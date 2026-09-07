"""Complete contemporaneous bookmaker markets; no cross-book margin removal."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.value.engine import classify_odds_prices, consensus_no_vig
from app.models import Event, OddsSnapshot
from app.research.features import timestamp
from app.research.validation import scores


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def market_at(
    session: AsyncSession, event: Event, at: datetime, *, max_age: timedelta = timedelta(minutes=30)
) -> dict[str, Any] | None:
    rows = list(
        await session.scalars(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.event_id == event.id,
                OddsSnapshot.market == "MONEYLINE",
                OddsSnapshot.point.is_(None),
                OddsSnapshot.is_live.is_(False),
                OddsSnapshot.is_outlier.is_(False),
                OddsSnapshot.validation_status == "VALID",
                OddsSnapshot.observed_at <= at,
                OddsSnapshot.observed_at >= at - max_age,
                OddsSnapshot.fetched_at <= at,
            )
            .order_by(OddsSnapshot.observed_at.desc())
        )
    )
    grouped: dict[tuple[str, datetime], dict[str, OddsSnapshot]] = defaultdict(dict)
    for row in rows:
        grouped[(row.bookmaker, row.observed_at)][row.selection] = row
    from app.models import Sport

    sport = await session.get(Sport, event.sport_id)
    if sport is None:
        return None
    selections = [event.home_name, event.away_name]
    if sport.key == "football":
        selections.insert(1, "Draw")
    books = {}
    ids: list[str] = []
    for (book, _), group in grouped.items():
        if book in books or set(group) != set(selections):
            continue
        books[book] = {key: group[key].decimal_odds for key in selections}
        ids.extend(group[key].id for key in selections)
    if len(books) < 2:
        return None
    rejected: set[str] = set()
    for selection in selections:
        classified = classify_odds_prices([v[selection] for v in books.values()])
        rejected.update(
            book for book, check in zip(books, classified, strict=True) if check.status != "VALID"
        )
    books = {k: v for k, v in books.items() if k not in rejected}
    if len(books) < 2:
        return None
    consensus = consensus_no_vig(list(books.values()))
    best = [max(v[s] for v in books.values()) for s in selections]
    return {
        "probabilities": [consensus[s] for s in selections],
        "best": best,
        "bookmakers": len(books),
        "snapshot_ids": ids,
        "selections": selections,
        "average": [mean(v[s] for v in books.values()) for s in selections],
        "median": [median(v[s] for v in books.values()) for s in selections],
        "latest_odds_at": max(aware(r.observed_at) for r in rows).isoformat(),
        "best_bookmakers": [max(books, key=lambda b: books[b][s]) for s in selections],
    }


async def attach_market_baseline(session: AsyncSession, report: dict[str, Any]) -> None:
    market_rows = []
    model_rows = []
    evidence = []
    profits: list[float] = []
    clvs: list[float] = []
    for row in report.get("out_of_sample", []):
        event = await session.get(Event, row["event_id"])
        if event is None:
            continue
        at = timestamp(row["start"]) - timedelta(seconds=1)
        if timestamp(row["latest_source_available_at"]) >= at:
            continue
        market = await market_at(session, event, at)
        if market is None:
            continue
        market_rows.append((market["probabilities"], row["outcome"]))
        model_rows.append((row["probabilities"], row["outcome"]))
        evidence.append({"event_id": event.id, "snapshot_ids": market["snapshot_ids"]})
        # Descriptive flat-stake research return, never a recommendation or ledger write.
        pick = max(
            range(len(row["probabilities"])),
            key=lambda i: row["probabilities"][i] * market["best"][i] - 1,
        )
        if row["probabilities"][pick] * market["best"][pick] - 1 >= 0.03:
            profits.append(market["best"][pick] - 1 if pick == row["outcome"] else -1)
        # No distinct execution timestamp is reconstructed; CLV is unavailable,
        # rather than comparing the same closing observation with itself.
    report["market_baseline"] = scores(market_rows)
    report["matched_model_metrics"] = scores(model_rows)
    report["market_comparison_samples"] = len(market_rows)
    report["market_evidence"] = evidence
    report["metrics"]["roi"] = sum(profits) / len(profits) if profits else None
    report["metrics"]["roi_basis"] = "HYPOTHETICAL_UNIT_STAKE_PRE_CLOSE_EV_3_PERCENT"
    report["metrics"]["clv"] = sum(clvs) / len(clvs) if clvs else None
