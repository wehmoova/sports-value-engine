# Sportmonks production ingestion repair

Root cause reproduced on 2026-09-07: the original fixture request included
`xGFixture` along with required fields. HTTP 403, code 5002, message:
`You do not have access to the 'xgfixture' include`.
The request failed before normalization/insert; the valid token was not the problem.

Now discovery reads all pages of `/leagues`, persists accessible IDs in API logs,
and queries only those leagues using `filters=fixtureLeagues:<id>` on
`fixtures/between/<from>/<to>`. Core includes: participants, league, state, scores.
Pagination is bounded and diagnostics omit next-page URLs and credentials.
Date window: 14 days before to 14 days after the actual run time.

Valid fixtures commit before optional enrichment. Statistics, lineups, standings,
and xG are probed independently; xG denial does not invalidate base ingestion.
Only returned fixture statistics are stored; per-match aggregates and historical
sample sizes are not invented. Lineups/standings capability probes currently test
access; they do not create dedicated normalized records in this repair.
Capability matrix is persisted in api_logs and exposed by `/system/status`.

Matching uses resolved team IDs (including unambiguous aliases), verified same
competition, and at most ten minutes kickoff difference. Multiple/uncertain matches
are not merged. Both event IDs remain in provider_entities. Historical duplicate
events are not destructively merged. Competition aliases require verified mappings.

Acceptance run: 56 Sportmonks fixture mappings and 24 statistic snapshots persisted;
accessible leagues 271, 501, 513, 1659; no normalization rejects. Example fixture
19713917, Horsens vs AGF, internal event eeafbd02-8e12-4336-bb89-9a1ac695e806.
This is local SQLite proof, not PostgreSQL/cloud certification.

Reproduce with `python -m app.scripts.verify_providers`, then
`python -m app.scripts.bootstrap_real_data`, then `python -m app.scripts.report_sportmonks`.
Report separates current-run provider counters from accumulated database totals.

Endpoint reference: https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-fixtures-by-date-range
