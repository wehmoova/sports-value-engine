import asyncio
import logging

import pytest

from app.services.job_lock import job_lock, waiting_job_lock


@pytest.mark.asyncio
async def test_replacement_waits_and_takes_over_only_after_release(caplog):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def replacement():
        async with waiting_job_lock("rolling-test", retry_seconds=0.001):
            entered.set()
            await release.wait()

    with caplog.at_level(logging.INFO):
        async with job_lock("rolling-test") as acquired:
            assert acquired
            task = asyncio.create_task(replacement())
            await asyncio.sleep(0.02)
            assert not entered.is_set()
        await asyncio.wait_for(entered.wait(), 1)
        async with job_lock("rolling-test") as second:
            assert not second
        release.set()
        await task
    assert sum("incumbent remains leader" in r.message for r in caplog.records) == 1


@pytest.mark.asyncio
async def test_cancelled_standby_does_not_release_incumbent():
    async def standby():
        async with waiting_job_lock("cancel-test", retry_seconds=0.001):
            pytest.fail("standby became leader")

    async with job_lock("cancel-test"):
        task = asyncio.create_task(standby())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with job_lock("cancel-test") as acquired:
            assert not acquired
    async with job_lock("cancel-test") as acquired:
        assert acquired
