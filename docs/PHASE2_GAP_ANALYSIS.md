# Phase 2 gap analysis

Audit date: 2026-09-02

## Working

- FastAPI/SQLAlchemy/Alembic and Next.js application boundaries are in place.
- The frontend reads only the internal FastAPI API; browser refreshes do not call sports providers.
- Core value mathematics (implied probability, proportional no-vig, fair odds, edge and EV) has deterministic unit tests.
- Football Poisson/Elo primitives, tennis overall/surface Elo primitives, chronological walk-forward splits, calibration metrics, bankroll and Monte Carlo utilities exist.
- Analysis-run locking, scheduler jobs, entity aliases and provider health records exist.
- Docker Compose describes frontend, backend and PostgreSQL services.

## Partial

- The Odds API adapter parses events and prices, but originally used the broad `upcoming` shortcut, did not discover active sports, omitted last-request cost and inserted duplicate snapshots.
- Entity resolution handles participants, but cross-provider event identity and source provenance were incomplete.
- Outlier handling rejected one extreme price but had no persisted `VALID`/`SUSPECT`/`REJECTED` classification or freshness gate.
- Model primitives are suitable for mathematical regression tests, but no validated trained production model or calibration artifact exists.
- Settlement and backtesting utilities exist, but automatic result ingestion and idempotent bankroll booking are not yet complete.

## Missing

- Production football-statistics and current-tennis adapters and their scheduled persistence path.
- Real-data bootstrap, provider diagnostic endpoint, per-step analysis-run audit and raw response audit metadata.
- Historical training datasets, calibrated model registry entries, out-of-sample model-vs-market reports and automatic model promotion.
- Automatic closing-line capture and complete settlement for every advertised market.

## Risky / needs validation

- No provider credentials are configured on this host, so live provider responses cannot be claimed as verified.
- Docker is not installed on this host. PostgreSQL container startup, empty-database migration and PostgreSQL-backed tests therefore remain unverified here.
- The existing local SQLite database contains legacy simulated seed rows. Real mode must remove or reject them before serving product data.
- No model may create a production recommendation until real pre-match statistics, adequate samples and calibration evidence are present.
