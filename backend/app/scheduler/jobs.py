from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.services.analysis import create_analysis_run, run_analysis


async def scheduled_analysis(job_type: str) -> None:
    run, created = await create_analysis_run("CRON", job_type)
    if created:
        await run_analysis(run.id)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        scheduled_analysis,
        CronTrigger(hour=6, minute=30, timezone=settings.app_timezone),
        args=["daily_analysis"],
        id="daily-analysis",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        scheduled_analysis,
        IntervalTrigger(
            minutes=settings.odds_sync_interval_minutes, timezone=settings.app_timezone
        ),
        args=["sync_odds"],
        id="odds-refresh",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        scheduled_analysis,
        IntervalTrigger(hours=2),
        args=["settle_events"],
        id="settlement",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
