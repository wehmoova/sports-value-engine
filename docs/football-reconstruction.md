# Football historical reconstruction v1

Feature version: `strict-historical-reconstruction-v1`.

Only `research features --sport football` and its read-only diagnosis select this
version. `strict-observed-v2`, Tennis, model training/validation/promotion logic and
live inference are unchanged. No schema migration is required. Research readiness
does not grant production eligibility or trigger any model operation.

## Central availability contract

`availability.py` defines `IMMUTABLE_EVENT_TIME` and `OBSERVED_SNAPSHOT_TIME`.
Football history artifacts must carry the stored raw payload, matching hash, run ID,
provider/fixture IDs, timezone-aware kickoff/observation timestamps and a verified
Sportmonks FT regulation result. Normalized scores and outcome must agree with raw
facts. Missing identities, competition/season, invalid scores and contradictory
versions fail closed. The same provider fixture mapped to different internal event
IDs is excluded rather than counted twice. Mutable raw statistics are never copied
into immutable features.

The schema has no verified match end timestamp. The approved conservative completion
bound is `min(first_observed_final, kickoff + 24 hours)`, with both kickoff and bound
strictly before the target kickoff. The 24-hour value is a documented reconstruction
assumption for validated FINAL fixtures, **not** an observed end time. A reliable
earlier final observation can establish an earlier bound. Ingestion/observation dates
are preserved verbatim in provenance; stored artifacts are never rewritten/backdated.
Conflicting result versions exclude the entire event and are counted in diagnosis.

Mutable team statistics/provider standings still pass the existing exact-event,
participant/provider mapping, hash and observation provenance loader. Effective
snapshot availability remains max(observed, fetched, source-updated), strictly before
kickoff. Post-match snapshots are not eligible. No ranking, injury, lineup, odds,
provider-form aggregate or xG is reconstructed from event time.

## Feature families

* Elo: initial 1500, K=24, fixed 60-point home advantage (untuned baseline assumptions).
  Compute each delta from kickoff-time state, apply it only once the result's
  completion bound is strictly earlier. Same-kickoff matches share pre-bucket state.
* Result/goal form: last 5 and 10 completed matches, actual sample counts, points per
  game (3/1/0), wins/draws/losses, mean goals for/against/difference.
* Home/away form: home team's home matches and away team's away matches; at least
  three each; rolling form over up to five, goal strengths over up to twenty.
* Opponent adjustment: mean actual-minus-expected Elo score over last ten matches,
  with opponent strength at each historical kickoff, never end-of-season rankings.
* Poisson inputs: earlier competition goal baselines (minimum 20 matches, may span
  seasons), venue attack/defence strengths and multiplicative goal rates. Explicit
  shrinkage of three league-average matches is a mathematical prior, not provider
  data and not xG. No model fitting or prediction is performed here.
* Reconstructed season state: sums of known completed results for the exact same
  competition/provider league/season. Counts, result-derived points and goals are
  labelled `PARTIAL_KNOWN_RESULTS_SAME_COMPETITION_SEASON`. No official rank,
  deductions, split-phase reset or full-schedule completeness is implied. No games
  in that season means unavailable, not a fabricated zero-standing.
* Observed provider team stats and standings are optional, with unchanged gates.
  xG remains unavailable (`None`, never an imputed real value).

Processing is sorted by kickoff and stable provider ID (not database insertion ID).
Every target selects strictly completed earlier sources; changing its own result,
future results or source-page order does not change its feature values.

## Diagnosis and operations

`research diagnose --sport football` executes in a read-only, repeatable-read
PostgreSQL transaction and does not persist artifacts. It uses the same builder.

`eligible_targets` means canonical valid final facts before warmup; `eligible_after_warmup`
means both minimum 200 prior results and minimum 10 per participant have passed.
Subsequent venue/league gates can still exclude samples. `exclusions` partitions
targets by first failing gate. `participant_warmup_targets` independently counts all
valid targets with inadequate participant history (overlaps global warmup exclusions).
Context-source counts are distinct used artifact/snapshot IDs across produced samples,
not the number of rows fetched. Coverage counts are numbers of produced samples.

After green tests/Ruff/MyPy, commit/push and confirm all three Railway services are
SUCCESS on the exact commit. Run diagnosis, inspect safety state, then exactly one
football feature build. STOP afterwards regardless of READY or INSUFFICIENT_DATA.
No training, validation, promotion, Tennis build or manual production migration.
