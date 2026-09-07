import asyncio

from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.models import AnalysisRun
from app.services.analysis import create_analysis_run, run_analysis
from app.services.data_mode import initialize_provider_statuses


async def execute(job_type: str, trigger: str = "CRON") -> int:
    async with SessionLocal() as session:
        await initialize_provider_statuses(session, settings)
    run, created = await create_analysis_run(trigger, job_type)
    if not created:
        print(f"SKIPPED: active run {run.id} ({run.status})")
        return 0
    await run_analysis(run.id)
    async with SessionLocal() as session:
        completed = await session.get(AnalysisRun, run.id)
        assert completed is not None
        print(f"{job_type}: {completed.status}; records={completed.records_processed}")
        return 0 if completed.status == "COMPLETED" else 1


def main(job_type: str) -> None:
    async def run() -> int:
        try:
            return await execute(job_type)
        finally:
            await engine.dispose()

    raise SystemExit(asyncio.run(run()))
