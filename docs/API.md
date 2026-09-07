# REST API surface

FastAPI publishes the authoritative OpenAPI contract at `/docs` and `/openapi.json`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/dashboard` | Aggregated daily market view |
| GET | `/api/v1/events` | Upcoming normalized events |
| GET | `/api/v1/events/{id}` | Event, verdict, model components and odds |
| GET | `/api/v1/football/events` | Football event board |
| GET | `/api/v1/tennis/events` | ATP/WTA event board |
| GET | `/api/v1/picks`, `/picks/today` | Qualified value candidates |
| GET | `/api/v1/picks/{id}` | One recommendation |
| GET | `/api/v1/no-bet` | Rejected price candidates and reason codes |
| GET | `/api/v1/combinations` | Qualified, capped combinations |
| GET | `/api/v1/odds/{event_id}` | Timestamped bookmaker snapshots |
| GET | `/api/v1/performance` | ROI, CLV, drawdown and calibration metrics |
| GET | `/api/v1/bankroll` | Bankroll history and drawdown |
| POST | `/api/v1/challenge/simulate` | Paper-trading Monte Carlo simulation |
| GET | `/api/v1/models` | Model segment health and enablement |
| GET | `/api/v1/system/status` | Runtime, provider and last-run health |
| GET | `/api/v1/providers/status` | Alias of the system health surface |
| POST | `/api/v1/analysis/run` | Queue a non-overlapping ingestion run |
| GET/POST | `/api/v1/settings` | Read or persist single-user thresholds |

