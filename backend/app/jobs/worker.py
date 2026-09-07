"""Persistent scheduler and durable manual-job consumer. No web process required."""

import asyncio
import logging
import signal
from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.models import AnalysisRun
from app.models.system import WorkerHeartbeat
from app.scheduler.jobs import build_scheduler
from app.services.analysis import run_analysis
from app.services.job_lock import job_lock, waiting_job_lock


async def heartbeat() -> None:
    while True:
        async with SessionLocal() as session:
            row = await session.get(WorkerHeartbeat, "scheduler")
            if row is None:
                row = WorkerHeartbeat(id="scheduler")
                session.add(row)
            row.last_seen = datetime.now(UTC)
            await session.commit()
        await asyncio.sleep(20)


async def serve() -> None:
    async with waiting_job_lock("worker-leader"):
        # Only recover RUNNING jobs after proving no execution owns the DB lock.
        async with job_lock("analysis-execute") as idle:
            if idle:
                async with SessionLocal() as session:
                    for run in await session.scalars(
                        select(AnalysisRun).where(AnalysisRun.status == "RUNNING")
                    ):
                        run.status = "FAILED"
                        run.finished_at = datetime.now(UTC)
                        run.log_summary = (
                            "Previous process ended before job completion; retry required."
                        )
                    await session.commit()
        scheduler = build_scheduler()
        if settings.worker_schedules_enabled:
            scheduler.start()
        pulse = asyncio.create_task(heartbeat())
        try:
            while True:
                if pulse.done():
                    await pulse  # Fail and restart if DB heartbeat cannot be written.
                async with SessionLocal() as session:
                    run_id = await session.scalar(
                        select(AnalysisRun.id)
                        .where(AnalysisRun.status == "QUEUED")
                        .order_by(AnalysisRun.created_at)
                    )
                if run_id:
                    await run_analysis(run_id)
                await asyncio.sleep(5)
        finally:
            if scheduler.running:
                scheduler.shutdown(wait=False)
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main() -> None:
        task = asyncio.create_task(serve())
        loop = asyncio.get_running_loop()
        # Railway sends SIGTERM on replacement. Cancel gracefully so finally blocks
        # release the leader session instead of waiting for the platform kill timeout.
        with suppress(NotImplementedError):
            loop.add_signal_handler(signal.SIGTERM, task.cancel)
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            await engine.dispose()

    asyncio.run(main())
