"""Each test session owns an isolated database; never mutate the developer database."""

import asyncio
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

_test_directory = tempfile.TemporaryDirectory(prefix="sve-tests-")
_test_url = os.environ.get("SVE_TEST_DATABASE_URL")
if _test_url and (
    not _test_url.startswith(("postgresql://", "postgresql+asyncpg://"))
    or not urlsplit(_test_url).path.endswith("_test")
):
    raise RuntimeError("Use a dedicated PostgreSQL test database with name ending in _test")
os.environ["DATABASE_URL"] = _test_url or (
    "sqlite+aiosqlite:///" + (Path(_test_directory.name) / "test.db").as_posix()
)
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["DATA_MODE"] = "real"
os.environ["ENABLE_MOCK_DATA"] = "false"
os.environ["ENABLE_SIMULATION"] = "false"


def pytest_sessionfinish() -> None:
    from app.database.session import engine

    asyncio.run(engine.dispose())
