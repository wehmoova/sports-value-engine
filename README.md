# Sports Value Engine

Production-oriented full-stack foundation for transparent pre-match sports analytics. The MVP supports football, ATP and WTA tennis, stores timestamped odds, removes bookmaker margin, calculates fair prices/edge/EV, and distinguishes value candidates from `NO BET`.

> Real provider data only. No guaranteed returns. Challenge simulations are isolated from production recommendations.

## Quick start

Historical research and worker rolling-deployment changes are documented in
[docs/RESEARCH.md](docs/RESEARCH.md). Migration `0004_research` adds durable checkpoints
and immutable research artifacts. No model is promoted automatically. Backfilled
data without proven historical availability cannot silently qualify a backtest.

Football point-in-time diagnostics, season-scoped provider statistics and bounded
dry-run/resumable backfills: [coverage runbook](docs/football-history-coverage.md).
No xG, training, promotion or availability-gate relaxation is part of this change.

1. Optionally copy `.env.example` to `.env` and add `THE_ODDS_API_KEY`.
2. Run `docker compose up --build` (it also works without `.env`).
3. Open [http://localhost:3001](http://localhost:3001), [http://localhost:8000/docs](http://localhost:8000/docs), or [http://localhost:8000/health](http://localhost:8000/health).

Without credentials the website shows empty real-data states: zero events, predictions and picks. No automatic seeding or demo fallback exists. Configured adapters are called by persisted jobs; historical training/calibration artifacts are not yet wired into production prediction generation. Market prices are never substituted for model probabilities.

## Architecture

```text
Provider adapters -> validation/normalization -> PostgreSQL
  -> sport models -> calibration-ready prediction records
  -> no-vig/value engine -> recommendations -> FastAPI -> Next.js
```

- `backend/`: FastAPI, SQLAlchemy 2, Alembic, analytics, provider adapters and scheduler.
- `frontend/`: Next.js App Router, TypeScript, Tailwind CSS, shadcn-style primitives, Lucide and Recharts.
- `docs/`: architecture, schema and API decisions.
- `scripts/`: developer checks.

The frontend never contacts sports or bookmaker providers. Provider keys stay in backend environment variables and are excluded from API responses and logs.

## Local development without Docker

Backend (uses local SQLite unless `DATABASE_URL` is set):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Quality checks

```bash
cd backend && pytest && ruff check app tests && mypy app
cd frontend && npm run lint && npm run build
```

## Current MVP scope

- Core navigation and responsive terminal-inspired dashboard.
- Dashboard, football, tennis, picks, event detail, odds, combinations, no-bet, performance, bankroll, challenge, settings and system pages.
- The Odds API adapter with retries, timeouts, stale/invalid price rejection, entity normalization and provider health.
- Configurable value thresholds, proportional no-vig probabilities, market consensus, robust price outlier filtering, EV and edge.
- Poisson/Elo football primitives, overall/surface tennis Elo, combination and Monte Carlo services.
- Persistent model/version timestamps, analysis runs, provider status, bankroll and settlement-ready records.
- APScheduler jobs and user-triggered analysis with concurrent-run protection.

## Real-data and cloud status

Provider adapters: The Odds API, Sportmonks/API-Football fallback, API Tennis.
Bootstrap: `python -m app.scripts.bootstrap_real_data` after `alembic upgrade head`.
Independent scheduler: `python -m app.jobs.worker`; production API does not schedule jobs.
Cloud configuration and exact environment variables: [Railway deployment](docs/DEPLOYMENT.md).
PostgreSQL is mandatory in production; SQLite is only a local/test exception.
Admin API writes require a server-side bearer token in production.

Limitations: no verified live provider request without keys; no active trained/calibrated
production model; historical backtest orchestration and explicit stake-ledger settlement
remain incomplete. Docker/Railway/PostgreSQL deployment must be verified externally.
Do not describe this foundation as a validated profitable system.
