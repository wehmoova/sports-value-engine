# Database schema

Entity resolution is centered on internal UUIDs. `provider_entities` maps a provider/type/external-id tuple to one internal sport entity; `entity_aliases` records normalized names without promoting provider strings to keys.

Main groups:

- Catalogue: `sports`, `competitions`, `teams`, `players`, `events`.
- Source traceability: `provider_entities`, `entity_aliases`, `api_logs`, `provider_status`.
- Features: `football_statistics`, `tennis_statistics`, `player_statistics`, `injuries`, `suspensions`, `lineups`.
- Market: append-only `odds_snapshots` with observed timestamps and live flag.
- Analytics: `model_predictions`, `recommendations`, `combination_recommendations`, `model_performance`, `analysis_runs`.
- User state: `users`, `user_settings`, `watchlists`, `notifications`, `bankroll_history`.
- Outcomes: `bet_results` carries prices at prediction/close, stake, P/L and settlement state.

The initial Alembic migration builds the complete metadata. Later revisions should use explicit generated operations as tables evolve.

