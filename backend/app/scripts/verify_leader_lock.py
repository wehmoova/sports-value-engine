"""Non-mutating PostgreSQL session-lock handover probe on an isolated lock name."""

import asyncio
import json
from uuid import uuid4

from app.database.session import engine
from app.services.job_lock import job_lock, waiting_job_lock


async def verify() -> int:
    if engine.dialect.name != "postgresql":
        print(json.dumps({"status": "NOT_VERIFIED", "reason": "PostgreSQL required"}))
        return 1
    name = f"leader-probe-{uuid4()}"
    entered, release = asyncio.Event(), asyncio.Event()

    async def candidate() -> None:
        async with waiting_job_lock(name, retry_seconds=0.1):
            entered.set()
            await release.wait()

    task: asyncio.Task[None] | None = None
    try:
        async with job_lock(name) as leader:
            assert leader
            task = asyncio.create_task(candidate())
            await asyncio.sleep(0.3)
            assert not entered.is_set()
        await asyncio.wait_for(entered.wait(), 5)
        async with job_lock(name) as competitor:
            assert not competitor
        release.set()
        await task
        print(
            json.dumps(
                {
                    "status": "VERIFIED",
                    "database": "postgresql",
                    "standby_waited": True,
                    "handover": True,
                    "exclusive": True,
                }
            )
        )
        return 0
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
