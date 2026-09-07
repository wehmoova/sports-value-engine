"""Read-only SQL evidence; local SQLite never certifies PostgreSQL."""

import asyncio
import json

from sqlalchemy import text

from app.database.session import engine


def acceptance_checks(dialect: str, counts: dict[str, int]) -> dict[str, bool]:
    """Connection alone is not evidence of a successful real-data bootstrap."""
    return {
        "postgresql": dialect == "postgresql",
        **{
            f"{table}_populated": counts.get(table, 0) > 0
            for table in ("events", "odds_snapshots", "football_statistics", "tennis_statistics")
        },
        "no_mock_events": counts.get("mock_events", -1) == 0,
    }


async def verify() -> int:
    try:
        async with engine.connect() as connection:
            counts = {}
            for table in (
                "events",
                "odds_snapshots",
                "provider_entities",
                "analysis_runs",
                "football_statistics",
                "tennis_statistics",
                "model_predictions",
                "recommendations",
            ):
                counts[table] = await connection.scalar(text(f"SELECT COUNT(*) FROM {table}"))
            counts["mock_events"] = await connection.scalar(
                text("SELECT COUNT(*) FROM events WHERE is_demo = true OR data_origin <> 'REAL'")
            )
            counts["successful_automatic_data_jobs"] = await connection.scalar(
                text(
                    "SELECT COUNT(*) FROM analysis_runs WHERE trigger = 'CRON' "
                    "AND status = 'COMPLETED' AND records_processed > 0"
                )
            )
            checks = acceptance_checks(engine.dialect.name, counts)
            verified = all(checks.values())
            print(
                json.dumps(
                    {
                        "database_engine": engine.dialect.name,
                        "counts": counts,
                        "acceptance_checks": checks,
                        "postgresql_status": "VERIFIED" if verified else "NOT_VERIFIED",
                    }
                )
            )
            return 0 if verified else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
