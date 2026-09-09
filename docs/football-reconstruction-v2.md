# Football reconstruction V2

`strict-historical-reconstruction-v2` is research-only. V1's modules and stored
datasets remain unchanged. Live inference and promotion gates are unchanged.
No schema migration, tennis change, xG, model training or promotion is part of this phase.

## Policy evidence (read-only production inspection, 2026-09-09)

234 canonical matches / 249 artifact versions, zero rejected immutable facts:
Superliga 25536: 192; Superliga 27897: 20; Premiership 28275: 22.
432 consecutive same-season team observations: median gap 7 days, maximum 66.08.
10 observed season transitions: 76–106.04 days. No competition switches observed
in this limited inventory; this is not proof that the provider history is complete.
December–February gaps of 61.96–66.08 days are consistent with a winter break.
May–August gaps span season boundaries. Sparse ingestion can also enlarge gaps.

Across 234 targets, both teams have at least 5 current-season matches in 162 cases,
at least 10 in 132, and sufficient venue-3 / league-20 Poisson history in 154.
After unchanged global-200 / participant-10 gates, 11 targets remain:
long-term team counts 32–35, current-season counts 0–3 (median 2), prior-season 32.
Their previous 30/60/90/120-day counts have medians 1/2/2/4 and maxima 2/3/3/5.
None has current-season Poisson coverage. This does not justify a 90-day cutoff.

## Versioned decisions

- Elo is isolated by internal competition AND provider league. Its 1500 prior,
  K=24, home offset=60 and strict completion-time updates reuse the frozen
  mathematical helper. Carry across seasons; no fitted offseason regression.
  A new competition gets its own 1500 state. Returning to a previously observed
  competition resumes only that competition's state; cup appearances do not reset
  or update league Elo. There is no inferred promotion/relegation rating transfer.
- Result, goal, opponent-adjusted and venue form use the current competition,
  provider league and season only. Rolling 5/10 means **up to** N real results,
  minimum 1, with actual counts and full-window flags. No previous-season fill.
- Sample eligibility retains the existing mandatory Poisson contract: at least
  three current-season home appearances for the home team, three away appearances
  for the away team and 20 league/season results, with positive goal baselines.
  Attack/defence use up to 20 respective venue matches. The existing 3-match
  baseline shrinkage is a model assumption, not synthetic match observations.
  `football_policy_v2.MINIMUMS` describes these fixed per-family thresholds.
- The global 200 and long-term participant 10 gates are unchanged. Global and
  participant counts may span competitions; they do not import other competitions
  into Elo, form or Poisson. Missing current-season coverage can still block a sample.
- Partial season ledgers are not official standings: no rank, stage reset,
  deductions or claim of complete season coverage.
- Opponent strength is the competition Elo at the historical kickoff, never its
  later rating. The short-term residual window remains current-season only.
- Season is the primary age boundary. Oldest form age, previous-match distance
  and within-season gaps are diagnosed, not silently truncated.
- Mutable snapshots keep the existing event/identity/provenance and maximum
  observed/fetched/source-updated timestamp gates. V2 additionally requires matching
  provider league and season. Missing scope fails closed. Existing callers retain
  the old context-loader output unless they explicitly request scope metadata.
- Family source IDs and coverage live in existing JSON, with unchanged immutable
  observation timestamps and the approved conservative completion-bound policy.

## Local pre-backfill impact

Canonical facts and 54 context records exported through a read-only repeatable-read
transaction were evaluated locally, without writing a production dataset.
V1 stored samples: 11. Actual V2 samples: **0**.
First exclusions: no prior 1; global history 200; participant history 22;
current-season Poisson coverage 11.
Post-warmup coverage: Elo 11 (including the explicit prior), short/goal/opponent
form 10, venue form 3, partial season ledger 10, Poisson 0, complete last-5/10 0.
No threshold was weakened to recover V1's sample count.

For the eleven V1 target IDs (prefixes below), result and goal windows use the
current-season counts; venue form and Poisson use the respective home/away counts.
All fall below the unchanged venue-3 / league-20 requirement:

| Target | Current season H/A | Poisson/venue H/A | League season |
| --- | --- | --- | --- |
| 066759ce | 1/1 | 1/0 | 5 |
| 0f2516c1 | 2/1 | 1/0 | 7 |
| daa216df | 1/1 | 0/1 | 7 |
| db6d4d48 | 1/2 | 1/0 | 7 |
| 9a105217 | 1/0 | 0/0 | 11 |
| 7bb436b1 | 2/2 | 0/1 | 12 |
| ad1a32d4 | 2/2 | 1/0 | 12 |
| d60f258a | 3/3 | 1/1 | 14 |
| ff4c5ecd | 1/3 | 0/1 | 15 |
| 440866ba | 3/2 | 2/1 | 15 |
| f464b838 | 3/3 | 1/1 | 19 |

Quality review: original V1 source files unchanged, 37 focused tests passed.
The full suite has 117 tests; Ruff and MyPy cover the backend (104 source files).

## Operation

`python -m app.scripts.research diagnose --sport football` is read-only and now
uses V2; `features --sport football` persists V2. V1 remains importable as
`app.research.football_reconstruction.build_dataset` for exact reproduction.
`python -m app.scripts.research audit --dataset ID` checks stored V2 samples
read-only, including exact reconstruction and source-window contamination.
An audit is not statistical model validation. The audit reports missing values,
duplicate targets, context scope, source timing and feature reproduction failures.
Backfill still uses the existing resumable paginated implementation; dry-run does
not estimate feature eligibility and returns null for that unknown sample count.

After the controlled historical backfill: diagnose, persist football features
exactly once, audit, then STOP. No training, validation or promotion.
