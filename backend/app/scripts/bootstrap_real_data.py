import asyncio

from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.services.analysis import create_analysis_run, run_analysis
from app.services.data_mode import initialize_provider_statuses
from app.services.queries import data_diagnostics, system_status


async def bootstrap() -> int:
    async with SessionLocal() as session:
        await initialize_provider_statuses(session, settings)
    run, created = await create_analysis_run("BOOTSTRAP")
    if not created:
        print(f"REAL DATA BOOTSTRAP NOT STARTED: active run {run.id} ({run.status})")
        return 2
    await run_analysis(run.id)
    async with SessionLocal() as session:
        diagnostics = await data_diagnostics(session)
        status = await system_status(session)
    print("REAL DATA BOOTSTRAP FINISHED — inspect status below")
    print(f"Run status: {status['last_analysis']['status']}")
    print(f"Real events: {diagnostics['real_events']}")
    print(f"Odds snapshots: {diagnostics['odds_snapshots']}")
    print(f"Football statistic snapshots: {diagnostics['football_statistics']}")
    print(f"Tennis statistic snapshots: {diagnostics['tennis_statistics']}")
    print(f"Predictions: {diagnostics['predictions']}")
    print(f"Recommendations: {diagnostics['recommendations']}")
    for provider in status["providers"]:
        print(
            f"{provider['name']}: {provider['status']} "
            f"(configured={provider['configured']}, records={provider['records_received']})"
        )
    await engine.dispose()
    return 0 if status["last_analysis"]["status"] in {"COMPLETED", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(bootstrap()))
