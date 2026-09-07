# Provider setup and live smoke test

Set secrets in Railway → project → backend → Variables and worker → Variables.
Alternatively use shared variables referenced by both services. Never set provider
secrets in frontend, NEXT_PUBLIC variables, committed files or command-line arguments.
Locally use an untracked backend/.env, then restart processes. Config loads root .env
and backend/.env when commands execute in backend; environment variables take precedence.

| Required secret | Provider / data | Where to add in Railway | Requirement |
|---|---|---|---|
| THE_ODDS_API_KEY | The Odds API: events and timestamped bookmaker odds | backend + worker Variables | Required for odds verification |
| SPORTMONKS_API_TOKEN | Sportmonks: football fixtures/statistics/availability | backend + worker Variables | Required if FOOTBALL_PROVIDER=sportmonks |
| API_FOOTBALL_KEY | API-Football: alternative football source | backend + worker Variables | Required if FOOTBALL_PROVIDER=api_football |
| API_TENNIS_KEY | API Tennis: matches/rankings/statistics | backend + worker Variables | Required for tennis verification |

Choose exactly one primary football provider. Set `FOOTBALL_PROVIDER=sportmonks`
with its token OR `FOOTBALL_PROVIDER=api_football` with its key. The other secret is
optional. Missing Sportmonks token falls back only if API_FOOTBALL_KEY exists.
Set `ODDS_PROVIDER=the_odds_api`, `TENNIS_PROVIDER=api_tennis`, `DATA_MODE=real`,
`ENABLE_MOCK_DATA=false`, `ENABLE_SIMULATION=false`.
Provider subscriptions must cover the competitions and included statistics requested.

From backend or the Railway remote backend shell:

```bash
python -m app.scripts.verify_providers
```

This makes real provider requests and may consume quota. It does not need a database.
JSON output contains actual HTTP status, received/validated counts and the first
validated event's external ID, participants, competition and timestamps. No sample
numbers are generated. Missing credentials return NOT_CONFIGURED; failures return
FAILED without raw exception text or secret-bearing URLs. An empty successful response
is REQUEST_SUCCEEDED_NO_EVENT_PROOF, not a fabricated event verification. Exit 0
requires event proof for all three selected sources; otherwise exit 1.

Next, on actual PostgreSQL:

```bash
alembic upgrade head
python -m app.scripts.bootstrap_real_data
python -m app.scripts.verify_real_data
python -m app.scripts.verify_database
```

Jobs are stored in `analysis_runs` (including job_type, trigger, records_processed),
not a separate `job_runs` table. See DEPLOYMENT.md for service variables, bootstrap,
worker startup and cloud acceptance. Zero predictions are acceptable; zero live data
without credentials is NOT end-to-end verification. Do not share secret values in chat.

## PostgreSQL test database (not yet executed here)

Create a fresh disposable database named `sve_test` on PostgreSQL. Never point tests
at the application database. In a dedicated remote test job, set both `DATABASE_URL`
and `SVE_TEST_DATABASE_URL` to this test database URL; set `ENVIRONMENT=test`.
Install backend development dependencies, run `alembic upgrade head`, then `pytest`.
The test runner accepts only PostgreSQL URLs whose database name ends in `_test`;
without SVE_TEST_DATABASE_URL it still uses temporary SQLite. Test connections use
NullPool to avoid sharing asyncpg connections between different test event loops.
Use a fresh test database for each run. Passing SQLite tests is not PostgreSQL proof.

After tests, run bootstrap using the separate application service DATABASE_URL.
Then compare `verify_database` counts against internal API responses, record a real
event ID and inspect that event on the website. Keep the cloud worker running until
a CRON-triggered run completes and persists data; only then stop local processes and
repeat cloud health/website checks. These acceptance steps remain unverified until
credentials and a Railway project are available.
