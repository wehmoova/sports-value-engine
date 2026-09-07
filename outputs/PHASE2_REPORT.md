# SPORTS VALUE ENGINE — implementation status, 2026-09-05

## IMPLEMENTED

Existing workspace updated, not replaced. Real-data configuration guards, provider
fallback, persistent jobs, separate worker, health endpoint, provenance UI, fresh-price
checks, no-demo empty states, cloud Docker startup and Railway deployment instructions.
This phase is NOT fully production-complete; open items below are material.

## REAL-DATA PIPELINE

The Odds API and football/tennis adapters are invoked by analysis/bootstrap jobs.
Events, odds and statistical snapshots persist via SQLAlchemy. Duplicate snapshots
are tested. Missing keys fail visibly. The price of a market is never used as a
substitute model probability. Feature/model/value stages currently remain SKIPPED:
historical training and calibrated artifact loading are not implemented end-to-end.
Simply adding a model-registry row does not activate an executable production model.

## MOCK DATA REMOVED

No automatic seed, no frontend sports-event arrays and no missing-key demo fallback.
Legacy flags remain for detection/cleanup, not generation. Domain words such as
fixture and sample_size represent real matches/statistical samples, not mock feeds.
Challenge Monte Carlo remains explicitly separate. Checked running DB: zero events,
odds, statistics, predictions, recommendations and mock records.
Removed two never-connected legacy provider-status stubs; a pre-migration local DB
backup exists at `work/pre-cloud-migration.sqlite.backup` (excluded from Git).

## PROVIDER STATUS

The Odds API, Sportmonks, API-Football, API Tennis: NOT_CONFIGURED.
No environment key and no root/backend `.env` was available.
ONLINE is set only after a successful sync request; absence of a model/class is not
treated as connectivity. API-Tennis price import is disabled because its current
payload does not establish quote observation time; timestamped tennis odds use Odds API.

## DATABASE STATUS

Local SQLite migrated successfully through `0003_cloud_jobs`, second upgrade a no-op.
Test sessions use isolated temporary SQLite databases, never the developer database.
Production rejects SQLite. PostgreSQL migration, cross-process advisory lock behavior,
FK enforcement and transaction semantics still require PostgreSQL acceptance testing.
Some older migrations use dynamic metadata; immutable migration history needs follow-up.

## CLOUD READINESS

Backend Docker start honors PORT on 0.0.0.0. Next standalone Docker supports runtime
PORT. Compose includes postgres/backend/frontend/worker and no demo flag.
CLI modules: sync_events, sync_odds, sync_statistics, daily_analysis, settle_events.
Worker heartbeat was observed ONLINE locally. Production writes require admin bearer
token; manual jobs are queued in DB and consumed by worker. Browser authentication
is not yet implemented, so production UI mutations are intentionally unauthorized.
`.railway/railway.ts` and its installed SDK pass TypeScript validation. No Railway
plan/apply or deployment was executed. Docker executable is unavailable here.

## TEST RESULTS

- Backend: 29 passed, 3 skipped; 56 dependency deprecation warnings on Python 3.14.
- Real provider integration selection: 3 skipped, missing credentials, no fake responses.
- Ruff: passed; MyPy: passed across 79 source files.
- Alembic: head `0003_cloud_jobs` on local SQLite; repeated upgrade successful.
- Frontend ESLint, TypeScript and Next.js production build: passed.
- Railway IaC TypeScript and SDK export checks: passed; remote plan not tested.
- HTTP smoke before final build: dashboard, football, tennis, picks, odds, combinations,
  avoid, performance, bankroll, challenge, system and settings all HTTP 200. No searched
  demo-team strings in those responses. No visual browser/E2E verification performed.
- Backend HTTP dashboard/events/picks/performance/diagnostics/health returned 200.
- Production `npm run start` attempt after final build was rejected by execution policy.
  The earlier development server was stopped for the build; port 3001 needs manual restart.
- Docker Compose runtime/config validation not executed: Docker is unavailable.

## REAL DATA VERIFICATION

The Odds API: NOT VERIFIED — KEY MISSING.
Football: NOT VERIFIED — KEY MISSING.
Tennis: NOT VERIFIED — KEY MISSING.
Local bootstrap correctly ended FAILED with all real counts zero. This is a
missing-credentials behavior test, NOT an end-to-end live-data success.

## KNOWN LIMITATIONS

Historical ingestion/training, calibration artifacts, production model execution and
full walk-forward/backtest orchestration remain incomplete. No production predictions
are generated, even if keys alone are supplied. Provider payload/coverage, pagination,
cross-provider entity resolution and optional enrichment failures need live acceptance.
sync_events and sync_statistics currently share enrichment, so are not cost-minimal.
Automatic settlement is disabled until an explicit stake ledger exists: recommendations
must not silently become placed bets or change real bankroll. Settlement math exists,
but complete result-provider → ledger → CLV/ROI evaluation is not finished.
SQLite locks are process-local only, explicitly not a production substitute.
Browser admin authentication, real event detail QA, Docker and Railway acceptance remain open.

## MANUAL STEPS REQUIRED

Follow `docs/DEPLOYMENT.md` for exact service creation, migration, bootstrap, scheduling
and acceptance commands. Backend AND worker variables:

```dotenv
ENVIRONMENT=production
DATA_MODE=real
ENABLE_MOCK_DATA=false
ENABLE_SIMULATION=false
DATABASE_URL=${{postgres.DATABASE_URL}}
THE_ODDS_API_KEY=<licensed key>
ODDS_PROVIDER=the_odds_api
FOOTBALL_PROVIDER=sportmonks
SPORTMONKS_API_TOKEN=<token or empty when using API-Football>
API_FOOTBALL_KEY=<key or empty when using Sportmonks>
TENNIS_PROVIDER=api_tennis
API_TENNIS_KEY=<licensed key>
ADMIN_API_TOKEN=<random secret of at least 32 bytes>
ALLOWED_ORIGINS=https://<frontend-domain>
APP_TIMEZONE=Europe/Berlin
SCHEDULER_ENABLED=false
WORKER_SCHEDULES_ENABLED=true
ODDS_SYNC_INTERVAL_MINUTES=30
DEPLOYMENT_VERSION=<release tag or commit SHA>
```

Backend additionally `PORT=8000`. Frontend only:

```dotenv
PORT=3001
HOSTNAME=0.0.0.0
INTERNAL_API_URL=http://backend.railway.internal:8000
NEXT_PUBLIC_API_URL=https://<backend-domain>
NEXT_PUBLIC_SITE_URL=https://<frontend-domain>
FRONTEND_URL=https://<frontend-domain>
```

Never put provider/admin tokens in the frontend. Configure Railway backups and alerts.
To reopen locally, run `npm run dev` from `frontend` (configured port 3001).
