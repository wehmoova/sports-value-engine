# Football historical coverage and observation contract

## Root cause verified in production (2026-09-08)

The previous dataset contains 41 unique history events and 24 loaded context rows.
These are different populations: statistics rows are not match results. The eight
completed historical checkpoints cover only 2026-08-01 and 2026-08-02 across four
accessible leagues; nine results came from that backfill. Normal scheduled ingestion
subsequently contributes final results from its rolling 14-day window.

The read-only production inspection found 42 unique history events (57 immutable
versions), 102 statistics rows, 48 rejected by provenance and 54 loaded context rows.
All 54 loaded rows are post-match, all have standings, none have goal rates. All 41
older targets have zero results observed before kickoff. The one newer target has
41 prior results, three appearances per participant and no pre-match context.
Thus all 42 fail the unchanged 200-prior-result gate; the participant minimum is 10.

The scheduler enriched the first 12 fixtures in provider order, starving upcoming
fixtures. Team requests retrieved season metadata without details, while the parser
expected API-Football's different shape. The fix prioritizes upcoming fixtures and
reads season-scoped Sportmonks details for types 52, 88 and 27263 only. Values are
provider observations, not reconstructed statistics. Ambiguous/missing samples fail
closed. Current standings never become historical standings for earlier kickoffs.

## No xG and no relaxed gates

`missing_features: ["xg", ...]` is descriptive coverage, NOT a rejection gate.
The existing `strict-observed-v2` feature version is retained. xG remains unavailable
(`None`, never imputed or consumed as a real zero); no xG endpoint/type is requested.
No parallel no-xG schema is necessary. The diagnosis explicitly reports
`xg_available=false` and `xg_is_required_gate=false`.

Results fetched today have `FIRST_OBSERVED_FINAL` availability today, even for an old
season. They may supply labels and history for later kickoffs, but cannot create
earlier feature evidence. Newly fetched historical fixture statistics are marked
post-match and never used as pre-match features of that fixture. Adding a large
backfill therefore does **not** promise immediately eligible training samples.

## Operational commands (backend directory)

```sh
python -m app.scripts.research diagnose --sport football
python -m app.scripts.research backfill --sport football --league 271 --season 25536 --from 2025-07-18 --to 2026-05-17 --window-days 14 --max-pages 10 --dry-run
python -m app.scripts.research backfill --sport football --league 271 --season 25536 --from 2025-07-18 --to 2026-05-17 --window-days 14 --max-pages 10 --resume
```

Production commands must use `railway.cmd ssh --service sports-value-engine
--environment production -- ...`, never `railway run`.

Diagnosis executes inside a repeatable-read/read-only PostgreSQL transaction, uses
the builder's actual first-failing gates and does not persist a dataset. Coverage
gaps are distinct from sample exclusions. Its snapshot inventory covers the source
table; rows outside target history are explicitly separate (including other tennis
tour rows when diagnosing tennis).

Dry-run makes real provider requests but never opens a DB session or job lock.
It reports the requested page budget and whether the range completed. Resume is
always on; the flag is explicit documentation. Original daily v1 checkpoints remain
valid. Windowed/season-filtered v2 keys include league, season, boundaries and page.
Raw-hash history identity prevents duplicate versions across overlapping windows.
Each page is transactional with a separate durable attempt and a recoverable cursor;
429 stops requests immediately. Resumption repeats the same command. No schema
change or manual migration is required.

Historical season discovery is not proof of every season's detailed access. A real
probe of league 271, season 25536, 2025-07-18 through 2025-07-24 returned six final
fixtures with statistics and 24 standings rows. These standings include multiple
stages; ambiguous team rows remain excluded. No historical pre-match availability
timestamp was established by this probe.

Provider shape reference:
https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/statistics/team-statistics

Stop after the single post-backfill football feature attempt, whether READY or
INSUFFICIENT_DATA. Do not train, promote, run tennis builds, or create predictions.
