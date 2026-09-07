import asyncio

from app.database.session import engine
from app.scripts.verify_current_run import verify_current_run
from app.services.analysis import create_analysis_run, run_analysis


async def verify() -> int:
    try:
        run, created = await create_analysis_run("ACCEPTANCE")
        if not created:
            print("NOT VERIFIED: another run is active")
            return 1
        await run_analysis(run.id)
        return 0 if await verify_current_run(run.id) else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
