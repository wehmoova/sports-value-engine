# Historical research and production gates

## Execution

Run from the backend directory or a migrated Railway backend container. PostgreSQL
is mandatory in production. CLI outputs artifact IDs needed by the next command.
Secrets remain in the service environment; never pass them as CLI arguments.

```bash
alembic upgrade head
python -m app.scripts.research backfill --sport football --start 2026-08-01 --end 2026-08-02 --max-pages 4
python -m app.scripts.research backfill --sport tennis --start 2026-08-01 --end 2026-08-02 --max-pages 4
python -m app.scripts.research features --sport football
python -m app.scripts.research features --sport tennis_atp
python -m app.scripts.research features --sport tennis_wta
python -m app.scripts.research train --dataset DATASET_ID --model football_elo
python -m app.scripts.research validate --trained TRAINED_ID
python -m app.scripts.research promote --validation VALIDATION_ID
python -m app.scripts.research status
```

Other baseline names: football_poisson, football_form, tennis_elo,
tennis_surface_elo, tennis_form. These are explicit simple baselines, not claims of
trained high-performance ML. Training freezes baseline parameters, then fits
temperature scaling on a later calibration partition; final evaluation does not
change parameters. Chronological Elo state evolves only using earlier available
results. Insufficient data and denied promotion return exit 1, not success.

## Durable backfill

Sportmonks discovers accessible leagues, then requests each date/league/page using
participants, league, state, scores and statistics.type. On optional statistics 403
it retries basic fixture includes. No xG request. Only final regulation scores with
provider participant IDs enter the research archive. Existing entity mapping is
reused; canonical collisions with different participants/competitions stay separate.

API Tennis uses UTC day partitions, only verified ATP/WTA singles and final winners.
Its documented fixtures endpoint has no pagination parameter; inventing one would
not establish completeness. Surface is kept only if actually returned. Raw fixture
statistics are preserved with provenance, not invented from ranking or score.

Each page's results, raw content hash, first-observed time and checkpoint commit
atomically. Completed pages are skipped on the same command; failed/incomplete pages
retry. Attempt outcomes persist separately. A max-pages cap returns PAUSED and a
resume key. Empty successful pages are cached. Reconciliation of later provider
corrections for already-completed backfill pages is not automatic; regular event
sync captures new observed final snapshots in its rolling date range.

Retry-After is honored. Waits above 60 seconds stop the request for later resumption;
do not repeatedly rerun a rate-limited provider. There are bounded retries and one
request/second default pacing, but no cross-account shared quota coordinator.
Historical backfill shares the analysis advisory lock to avoid competing writes.

## Point-in-time contract and limitations

Result snapshots use FIRST_OBSERVED_FINAL as availability. A retrieved final score
does **not** prove it was available at a historical kickoff. No arbitrary match
duration, backdated fetched timestamp, current ranking, final season standings,
post-match statistics of the target, or closing price is made into a past feature.

Consequently a new historical backfill may produce zero strict training samples.
This is intentional. A provider-verified point-in-time archive or accumulated
prospective result snapshots is needed before valid out-of-sample evidence exists.
Current production events outside the archive are counted separately, not claimed
as training samples. Backfill counts are unique events, not statistic snapshots.

Implemented features: chronological Elo, football home advantage, regularized
goal-for/against home/away Poisson strength, recent form, side-specific form and rest
intervals. Tennis adds surface Elo only after enough surface matches, plus H2H only
after five prior encounters. ATP and WTA datasets are separate. Prospective provider
snapshots can additionally supply tennis ranking/ranking-point deltas and football
team goal-rate and standings deltas. Exact-event context is used only when its
observed, fetched and provider-updated timestamps are all strictly before the feature
cutoff. Current/final season values are never backdated; a historical result backfill
alone therefore cannot reconstruct these features. Missing provider fields stay null.
Opponent-adjusted rolling ancillary statistics and xG stay absent. Elo itself adjusts
for opponent strength; goal estimates are not presented as measured xG.

The feature builder reconstructs histories conservatively and currently has quadratic
cost; use bounded research windows, not unbounded multi-year jobs on the worker.

## Validation and promotion

60% initial partition, 20% calibration, last 20% unseen chronological prequential
evaluation. Labels used in calibration must be observed before test begins. Equal
kickoffs cannot straddle train/test groups in the walk-forward split utility.
Persisted datasets record exact contributing history artifact/statistic snapshot IDs,
feature version, context evidence counts and per-feature coverage.

### Context v2 safety and compatibility

The patch was checked against `9ea2f40` before application. Context v2 also verifies
the snapshot's provider-entity mapping, event participant side, sport and real-data
origin. The stored payload hash must match the payload, and the prospective
`OBSERVED_PROVIDER_SNAPSHOT` provenance marker and ingestion run must exist. Legacy
snapshots without this evidence are excluded, not retroactively upgraded. Used
context timestamps, provider IDs, hashes and source table names are copied into the
dataset's `context_provenance` alongside snapshot IDs.

Unavailable/invalid times, nonfinite numbers, invalid ranking positions, simultaneous
conflicting snapshots and ambiguous standings groups fail closed. Team goal-rate
features require a positive sample count. Rank/standings pairs must come from the
same provider; ATP and WTA ranking maps are kept separate. Missing season IDs are
not replaced with the current year. Unchanged consecutive snapshots are deduplicated;
an A-to-B-to-A change creates a new observation with a new availability time.

No schema migration is required. Feature version is now `strict-observed-v2`; existing
v1 production artifacts cannot pass the inference feature-version check. The current
baseline probability functions still consume their original Elo/Poisson/form inputs,
not the newly collected context covariates. Training a model that uses these
additional covariates and obtaining historical point-in-time coverage remain separate
work. No promotion thresholds are relaxed by this patch.

Brier is half the sum of squared class errors (equals usual binary Brier); log loss
is multiclass, calibration/ECE is top-label reliability in ten bins. Market baseline
requires two complete, timestamp-matched bookmaker markets observed and fetched
before cutoff, no-vig per bookmaker then consensus. Outliers are rejected.
ROI is explicitly hypothetical flat-unit EV research, not actual bankroll performance.
CLV compares earlier persisted recommendation prices for the exact model version
against verified final-five-minute best prices. It remains null without both
observations; recommendation price CLV is not evidence of an executed wager.

Promotion is never a scheduler action. Explicit CLI promotion recomputes evidence
and checks configured sample/Brier/log-loss/ECE thresholds, sufficient matched market
coverage and better Brier AND log loss than the matched market. Failed attempts are
audited as NO_PRODUCTION_MODEL. Success retires the previous active sport model and
registers the artifact as PRODUCTION. Thresholds are initial conservative policy,
not a statistical significance claim. Multiple-testing correction and confidence
intervals are future work; do not promote based on repeated holdout tuning.

Daily inference loads only promoted calibrated artifacts, expires promotion after
30 days, rebuilds features at prediction time and requires fresh complete markets.
Without a model/probability or sufficient data quality it creates no output. The
conservative deterministic quality score gives no points for absent availability
coverage. Predictions are immutable per event/model/selection; price-triggered
re-entry after a NO BET needs a later extension. No LLM sets probabilities.

## Worker rollout

The replacement waits five seconds between advisory-lock attempts and logs at most
once per minute. Failed lock attempts release their DB connection before waiting.
No scheduler/heartbeat/job recovery runs before acquiring leadership. SIGTERM cancels
the Linux worker cleanly and releases the incumbent's lock. No lease stealing.
SQLite test locks are process-local; they do not certify PostgreSQL cross-process
semantics. Deploy additive migration before relying on the new research commands.

## Sources

- https://api-tennis.com/documentation
- https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-all-fixtures
- https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/statistics/statistics-types
