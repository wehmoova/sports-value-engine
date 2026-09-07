"""Session-scoped PostgreSQL locks survive commits within a job, not process death."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256

from sqlalchemy import text

from app.database.session import engine

_local_locks: dict[str, asyncio.Lock] = {}


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
