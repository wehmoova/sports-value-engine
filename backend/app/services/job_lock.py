"""Session-scoped PostgreSQL locks survive commits within a job, not process death."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from time import monotonic

from sqlalchemy import text

from app.database.session import engine

_local_locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def waiting_job_lock(
    name: str, *, retry_seconds: float = 5, log_interval_seconds: float = 60
) -> AsyncIterator[None]:
    """Stand by without a DB connection; never steal an incumbent's session lock."""
    if retry_seconds <= 0 or log_interval_seconds <= 0:
        raise ValueError("Lock retry and logging intervals must be positive")
    next_log = 0.0
    while True:
        async with job_lock(name) as acquired:
            if acquired:
                yield
                return
        if monotonic() >= next_log:
            logging.getLogger(__name__).info("Waiting for %s; incumbent remains leader", name)
            next_log = monotonic() + log_interval_seconds
        await asyncio.sleep(retry_seconds)


@asynccontextmanager
async def job_lock(name: str) -> AsyncIterator[bool]:
    if engine.dialect.name != "postgresql":
        # Development only. Production configuration rejects SQLite.
        lock = _local_locks.setdefault(name, asyncio.Lock())
        if lock.locked():
            yield False
            return
        async with lock:
            yield True
        return
    key = int.from_bytes(sha256(name.encode()).digest()[:8], "big", signed=True)
    async with engine.connect() as connection:
        acquired = bool(
            await connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
        )
        await connection.commit()
        try:
            yield acquired
        finally:
            if acquired:
                await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                await connection.commit()
