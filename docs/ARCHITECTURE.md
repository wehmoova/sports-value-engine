# Architecture decisions

## Product boundary

The web application is the product. Only backend workers call external providers. API handlers read normalized persisted records, so page loads never spend provider quota and historical recommendations remain reproducible.

## Runtime components

| Component | Responsibility |
| --- | --- |
| Next.js | Server-rendered analytical workspace and client interactions |
| FastAPI | Typed REST API, orchestration and health surface |
| PostgreSQL | Normalized entities, snapshots, predictions and results |
| APScheduler | Daily ingestion/analysis and periodic odds refresh |
| Provider adapters | External schemas, retries, rate limits and validation |
| Sport pipelines | Feature calculation and independent model outputs |
| Value engine | Consensus, no-vig, fair odds, edge, EV and filters |

## Model governance

Every prediction carries model version, feature version, training period, prediction time and data-snapshot time. Closing prices are stored only as later snapshots and are not available to pre-match feature builders. Confidence and data-quality scores are deterministic composites; missing xG, lineup, injury or serve/return data reduces the score and can force `NO BET`.

The initial provider-only flow intentionally creates no wager recommendation from market odds alone. Simulated seed records demonstrate the UI and are flagged end-to-end.

## Security and reliability

- Provider credentials exist only in backend environment variables.
- Production CORS uses an explicit origin list.
- Adapter calls use bounded timeouts, retry with exponential backoff and provider-health persistence.
- Odds outside plausible decimal ranges, stale snapshots and robust median-deviation outliers are rejected or flagged.
- Analysis-run locking prevents overlapping manual and scheduled runs.

