# Railway deployment — staging first

Status: container/cloud execution prepared, NOT deployed or verified on Railway.
The application currently supports real ingestion and guarded empty predictions.
Historical training/calibration artifact loading and automatic stake-ledger settlement
are not complete. Do not present this deployment as a validated betting model.

## 1. Repository and services

1. Create a private GitHub repository containing this workspace. Review `.gitignore`;
   never add `.env`, databases, backups, provider keys or `work/`.
2. Create a Railway project, add PostgreSQL and enable database backups.
3. Connect that repository to a service named `backend`, root directory `/backend`.
   Railway detects its Dockerfile. Set pre-deploy command `alembic upgrade head`.
   Keep the Dockerfile start command: it binds `0.0.0.0` and honors `PORT`.
   Set `PORT=8000`, healthcheck `/health`, one replica, restart on failure.
4. Create `worker` from the same repository and root `/backend`. Start command:
   `python -m app.jobs.worker`. No public domain or HTTP healthcheck. One replica,
   restart on failure, no sleeping/serverless. Start only after backend migration succeeds.
5. Create `frontend`, root `/frontend`, Dockerfile build. Start command comes from
   Dockerfile (`node server.js`, Next standalone). Set `PORT=3001`, healthcheck
   `/dashboard`. Generate public HTTPS domains for frontend and backend.
6. Set environment variables below, redeploy backend then worker then frontend.
   Frontend public variables are build-time values: changing them requires rebuild.

No local process is needed after deployment. Keep database private. Do not use a
transaction-pooling proxy for session-level advisory locks; use direct PostgreSQL.

## 2. Exact variables

Backend AND worker:

```dotenv
ENVIRONMENT=production
DATA_MODE=real
ENABLE_MOCK_DATA=false
ENABLE_SIMULATION=false
DATABASE_URL=${{postgres.DATABASE_URL}}
THE_ODDS_API_KEY=<licensed Odds API key>
ODDS_PROVIDER=the_odds_api
FOOTBALL_PROVIDER=sportmonks
SPORTMONKS_API_TOKEN=<Sportmonks token, or empty if using API-Football>
API_FOOTBALL_KEY=<API-Football key, or empty if using Sportmonks>
TENNIS_PROVIDER=api_tennis
API_TENNIS_KEY=<API Tennis key>
ADMIN_API_TOKEN=<independently generated random secret of at least 32 bytes>
ALLOWED_ORIGINS=https://<frontend-domain>
APP_TIMEZONE=Europe/Berlin
SCHEDULER_ENABLED=false
WORKER_SCHEDULES_ENABLED=true
ODDS_SYNC_INTERVAL_MINUTES=30
DEPLOYMENT_VERSION=<release tag or commit SHA>
```

Backend additionally `PORT=8000`. Missing Sportmonks token plus available
API-Football key selects API-Football, never simulated data. Missing all keys is
a valid empty setup, NOT verified connectivity. Blank/SQLite production DB is rejected.

Frontend ONLY (never copy backend secrets):

```dotenv
PORT=3001
HOSTNAME=0.0.0.0
INTERNAL_API_URL=http://backend.railway.internal:8000
NEXT_PUBLIC_API_URL=https://<backend-domain>
NEXT_PUBLIC_SITE_URL=https://<frontend-domain>
FRONTEND_URL=https://<frontend-domain>
```

For the optional `.railway/railway.ts` IaC template, first create shared variables:
`ADMIN_API_TOKEN`, `THE_ODDS_API_KEY`, `SPORTMONKS_API_TOKEN`, `API_FOOTBALL_KEY`,
`API_TENNIS_KEY`, `FRONTEND_URL`, `PUBLIC_BACKEND_URL`, `DEPLOYMENT_VERSION`.
Set unused alternative provider keys to empty strings. In the CLI environment set
`SVE_GITHUB_REPO=owner/repository`, install the dependency in `.railway`, authenticate,
link the intended project, and run `railway config plan`. Review every change before
`railway config apply`. This template has NOT been applied or remotely validated.

## 3. Migrations and bootstrap

Run migrations once in backend pre-deploy, not concurrently in every worker.
In a Railway remote backend shell (not a local shell with private-network variables):

```bash
alembic current
python -m app.scripts.bootstrap_real_data
python -m app.scripts.verify_real_data
python -m app.scripts.verify_database
```

Expect head `0003_cloud_jobs`. Bootstrap prints persisted counts and each provider's
status. Exit 1 for missing credentials/failed sync is intentional. Verification
requires current-run provider evidence, event and odds on PostgreSQL; it does not
certify model performance or browser rendering. Back up existing data before migration.
Unique-index migration fails on existing duplicates instead of silently deleting records.
`verify_database` exits successfully only for PostgreSQL with populated events, odds,
football statistics and tennis statistics, and zero mock events. Its CRON count is
separate evidence: a successful bootstrap does not certify automatic cloud execution.

Manual remote sync: `POST /api/v1/admin/sync-real-data` with header
`Authorization: Bearer <ADMIN_API_TOKEN>`. Production queues the run in PostgreSQL;
worker executes it. Read `/api/v1/system/status` for status and steps.
Browser mutations are intentionally unauthorized until user/session authentication
is implemented; do not put the admin token in `NEXT_PUBLIC_*` or frontend code.

## 4. Scheduling

Recommended: keep the persistent worker. It polls manual jobs, writes heartbeat
every 20 seconds, schedules daily analysis at 06:30 Europe/Berlin, odds updates
every `ODDS_SYNC_INTERVAL_MINUTES`, and result-refresh jobs every two hours.
Separate worker-leader, enqueue and execution advisory locks protect overlapping
processes. A restarted leader marks abandoned RUNNING jobs failed, preserving audit.
Monitor failed runs; automatic retries of abandoned work are not yet implemented.

Explicit one-shot alternatives, run inside the backend image:

```bash
python -m app.jobs.sync_events
python -m app.jobs.sync_statistics
python -m app.jobs.sync_odds
python -m app.jobs.daily_analysis
python -m app.jobs.settle_events
```

Events/statistics currently share provider enrichment and are not minimal-cost separate
pipelines. `sync_odds` invokes only the odds provider. Result refresh does not invent
stakes or book user P/L. Automatic settlement is deliberately disabled without a ledger.

If using Railway Cron instead, set `WORKER_SCHEDULES_ENABLED=false` on the worker first;
do NOT enable both schedules. Configure each one-shot service under Settings → Cron
Schedule, restart policy NEVER, no HTTP healthcheck. Example UTC schedules:
daily `30 4 * * *`, odds `*/30 * * * *`, settlement `15 */2 * * *`.
UTC schedules do not track Berlin daylight saving. Keep a queue-consuming worker or
execute manual bootstrap directly; cron-only services do not consume manual queue rows.

## 5. Acceptance and monitoring

Request backend `/health` and `/api/v1/system/health`, then
`/api/v1/system/data-diagnostics`. Verify real mode, database ONLINE, heartbeat less
than 90 seconds old, correct provider statuses, no mock records and growing real
snapshot counts after successful licensed requests. `/health` is startup readiness;
the detailed endpoint distinguishes SETUP_REQUIRED/DEGRADED and worker state.

Open frontend `/dashboard`, `/football`, `/tennis`, `/system` and an actual event URL.
Confirm source times and actual odds. No credentials must leave zero predictions.
Re-run migration twice and sync twice, compare duplicate counts, then run two jobs
concurrently against PostgreSQL to validate locks. This host did not have Docker or
PostgreSQL available, so these container/PostgreSQL checks remain required.

Keep frontend/backend logs, configure external health alerts and provider quota alarms.
Model activation requires historical walk-forward validation and calibration first.

## Official Railway references

Dockerfiles and dashboard service settings are the primary setup above. Railway's
current documentation describes IaC as the replacement for legacy config files:
[IaC](https://docs.railway.com/infrastructure-as-code),
[pre-deploy](https://docs.railway.com/deployments/pre-deploy-command),
[cron lifecycle and UTC](https://docs.railway.com/cron-jobs).
