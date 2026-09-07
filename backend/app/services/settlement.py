from collections import defaultdict
from datetime import UTC, datetime
from statistics import median

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.bankroll import settle_profit
from app.models import BankrollHistory, BetResult, Event, OddsSnapshot, Recommendation


def price_clv(prediction_odds: float, closing_odds: float) -> float:
    if prediction_odds <= 1 or closing_odds <= 1:
        raise ValueError("CLV prices must be greater than one")
    return prediction_odds / closing_odds - 1


def probability_clv(prediction_odds: float, closing_odds: float) -> float:
    if prediction_odds <= 1 or closing_odds <= 1:
        raise ValueError("CLV prices must be greater than one")
    return 1 / closing_odds - 1 / prediction_odds


def _single_line_result(value: float) -> str:
    if value > 0:
        return "WIN"
    if value < 0:
        return "LOSS"
    return "PUSH"


def _asian_components(point: float) -> tuple[float, ...]:
    quarter = round(point * 4)
    if quarter % 2 == 0:
        return (point,)
    lower = (quarter - 1) / 4
    upper = (quarter + 1) / 4
    return (lower, upper)


def _combine_asian(results: tuple[str, ...]) -> str:
    if len(results) == 1:
        return results[0]
    values = {"WIN": 1, "PUSH": 0, "LOSS": -1}
    total = sum(values[result] for result in results)
    if total == 2:
        return "WIN"
    if total == 1:
        return "HALF_WIN"
    if total == -1:
        return "HALF_LOSS"
    if total == -2:
        return "LOSS"
    return "PUSH"


def settle_market(
    *,
    market: str,
    selection: str,
    home_name: str,
    away_name: str,
    home_score: float | None,
    away_score: float | None,
    winner_name: str | None,
    point: float | None = None,
) -> str:
    normalized_market = market.upper()
    normalized_selection = selection.strip().lower()
    if normalized_market in {"MONEYLINE", "1X2"}:
        if normalized_selection not in {home_name.lower(), away_name.lower(), "draw"}:
            raise ValueError("Unknown moneyline selection")
        if winner_name:
            return "WIN" if normalized_selection == winner_name.lower() else "LOSS"
        if home_score is None or away_score is None:
            raise ValueError("Verified result missing")
        winner = (
            home_name
            if home_score > away_score
            else away_name
            if away_score > home_score
            else "Draw"
        )
        return "WIN" if normalized_selection == winner.lower() else "LOSS"
    if home_score is None or away_score is None or point is None:
        raise ValueError("Verified result or market line missing")
    if normalized_market in {"TOTALS", "TOTAL"}:
        if not normalized_selection.startswith(("over", "under")):
            raise ValueError("Unknown total selection")
        total = home_score + away_score
        is_over = normalized_selection.startswith("over")
        results = tuple(
            _single_line_result(total - component if is_over else component - total)
            for component in _asian_components(point)
        )
        return _combine_asian(results)
    if normalized_market in {"HANDICAP", "ASIAN_HANDICAP"}:
        if normalized_selection not in {home_name.lower(), away_name.lower()}:
            raise ValueError("Unknown handicap selection")
        selected_home = normalized_selection == home_name.lower()
        selected_score = home_score if selected_home else away_score
        opponent_score = away_score if selected_home else home_score
        results = tuple(
            _single_line_result(selected_score + component - opponent_score)
            for component in _asian_components(point)
        )
        return _combine_asian(results)
    raise ValueError("Unsupported settlement market")


async def capture_closing_odds(session: AsyncSession, event: Event) -> int:
    rows = list(
        (
            await session.execute(
                select(OddsSnapshot)
                .where(
                    OddsSnapshot.event_id == event.id,
                    OddsSnapshot.validation_status == "VALID",
                    OddsSnapshot.observed_at <= event.start_time,
                )
                .order_by(OddsSnapshot.observed_at)
            )
        ).scalars()
    )
    latest_by_book: dict[tuple[str, str, float | None, str], OddsSnapshot] = {}
    for row in rows:
        latest_by_book[(row.market, row.selection, row.point, row.bookmaker)] = row
    grouped: dict[tuple[str, str, float | None], list[float]] = defaultdict(list)
    for (market, selection, point, _), row in latest_by_book.items():
        grouped[(market, selection, point)].append(row.decimal_odds)
    recommendations = list(
        (
            await session.execute(select(Recommendation).where(Recommendation.event_id == event.id))
        ).scalars()
    )
    updated = 0
    for recommendation in recommendations:
        prices = grouped.get(
            (recommendation.market, recommendation.selection, recommendation.market_point), []
        )
        if not prices:
            continue
        recommendation.closing_best_odds = max(prices)
        recommendation.closing_consensus_odds = median(prices)
        updated += 1
    await session.flush()
    return updated


async def settle_finished_events(session: AsyncSession, stake: float | None = None) -> int:
    # A recommendation is not a placed bet. Until a stake ledger exists, require
    # an explicit stake from the caller and never silently debit user bankrolls.
    if stake is None:
        return 0
    if stake <= 0:
        raise ValueError("Stake must be positive")
    events = list(
        (
            await session.execute(
                select(Event).where(
                    Event.status == "FINAL",
                    Event.is_demo.is_(False),
                    Event.data_origin == "REAL",
                )
            )
        ).scalars()
    )
    settled = 0
    for event in events:
        await capture_closing_odds(session, event)
        recommendations = list(
            (
                await session.execute(
                    select(Recommendation).where(
                        Recommendation.event_id == event.id,
                        Recommendation.status == "VALUE",
                        Recommendation.is_demo.is_(False),
                    )
                )
            ).scalars()
        )
        for recommendation in recommendations:
            existing = await session.scalar(
                select(BetResult).where(BetResult.recommendation_id == recommendation.id)
            )
            if existing is not None:
                continue
            result = settle_market(
                market=recommendation.market,
                selection=recommendation.selection,
                home_name=event.home_name,
                away_name=event.away_name,
                home_score=event.home_score,
                away_score=event.away_score,
                winner_name=event.winner_name,
                point=recommendation.market_point,
            )
            closing = recommendation.closing_best_odds
            bet_result = BetResult(
                recommendation_id=recommendation.id,
                result=result,
                odds_at_prediction=recommendation.prediction_odds or recommendation.best_odds,
                closing_odds=closing,
                stake=stake,
                profit_loss=settle_profit(
                    result=result, stake=stake, decimal_odds=recommendation.best_odds
                ),
                settled_at=datetime.now(UTC),
            )
            session.add(bet_result)
            await session.flush()
            latest_bankroll = await session.scalar(
                select(BankrollHistory).order_by(desc(BankrollHistory.recorded_at))
            )
            if latest_bankroll is not None:
                session.add(
                    BankrollHistory(
                        user_id=latest_bankroll.user_id,
                        bankroll=latest_bankroll.bankroll + bet_result.profit_loss,
                        change=bet_result.profit_loss,
                        reason="RECOMMENDATION_SETTLEMENT",
                        bet_result_id=bet_result.id,
                    )
                )
            settled += 1
    await session.flush()
    return settled
