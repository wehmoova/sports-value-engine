from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    AnalysisRun,
    BankrollHistory,
    BetResult,
    CombinationRecommendation,
    Competition,
    Event,
    FootballStatistic,
    Injury,
    Lineup,
    ModelPerformance,
    ModelPrediction,
    OddsSnapshot,
    PlayerStatistic,
    ProviderStatus,
    Recommendation,
    Suspension,
    TennisStatistic,
)

PROVIDERS = (
    ("The Odds API", "the_odds_api"),
    ("Sportmonks", "sportmonks"),
    ("API-Football", "api_football"),
    ("API Tennis", "api_tennis"),
)


def provider_is_configured(settings: Settings, key: str) -> bool:
    return {
        "the_odds_api": bool(settings.the_odds_api_key),
        "sportmonks": bool(settings.sportmonks_api_token),
        "api_football": bool(settings.api_football_key),
        "api_tennis": bool(settings.api_tennis_key),
    }[key]


async def initialize_provider_statuses(session: AsyncSession, settings: Settings) -> None:
    await session.execute(
        delete(ProviderStatus).where(
            ProviderStatus.provider_name.in_(["Football statistics", "Tennis statistics"]),
            ProviderStatus.last_success.is_(None),
        )
    )
    for display_name, key in PROVIDERS:
        configured = provider_is_configured(settings, key)
        item = await session.scalar(
            select(ProviderStatus).where(ProviderStatus.provider_name == display_name)
        )
        if item is None:
            item = ProviderStatus(provider_name=display_name)
            session.add(item)
        item.configured = configured
        if not configured:
            item.status = "NOT_CONFIGURED"
            item.last_error = f"Missing server credential for {key}."
        elif item.last_success is None:
            item.status = "OFFLINE"
            item.last_error = "Configured but no successful provider request recorded."
    await session.commit()


async def purge_legacy_simulation_records(session: AsyncSession) -> int:
    """Remove records created by the retired automatic demo seed.

    The operation is intentionally narrow: only rows explicitly marked as demo/simulated
    or attached to a demo event are touched.
    """
    demo_event_ids = list(
        (await session.scalars(select(Event.id).where(Event.is_demo.is_(True)))).all()
    )
    deleted = len(demo_event_ids)
    if demo_event_ids:
        recommendation_ids = list(
            (
                await session.scalars(
                    select(Recommendation.id).where(Recommendation.event_id.in_(demo_event_ids))
                )
            ).all()
        )
        if recommendation_ids:
            await session.execute(
                delete(BetResult).where(BetResult.recommendation_id.in_(recommendation_ids))
            )
        for model in (
            Recommendation,
            ModelPrediction,
            OddsSnapshot,
            FootballStatistic,
            TennisStatistic,
            Injury,
            Suspension,
            Lineup,
            PlayerStatistic,
        ):
            if hasattr(model, "event_id"):
                await session.execute(delete(model).where(model.event_id.in_(demo_event_ids)))
        await session.execute(delete(Event).where(Event.id.in_(demo_event_ids)))
    await session.execute(
        delete(CombinationRecommendation).where(CombinationRecommendation.is_demo.is_(True))
    )
    await session.execute(delete(BankrollHistory).where(BankrollHistory.reason.like("SIMULATED%")))
    await session.execute(
        delete(ModelPerformance).where(ModelPerformance.segment.like("%SIMULATED%"))
    )
    await session.execute(delete(AnalysisRun).where(AnalysisRun.trigger == "DEMO_SEED"))
    await session.execute(
        delete(Competition).where(
            (Competition.country == "Demo") | (Competition.external_key.like("demo_%"))
        )
    )
    await session.commit()
    return deleted
