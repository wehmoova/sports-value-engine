"""Synthetic regression data exclusively for tests; never ingested in production."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.providers.odds.the_odds_api import payload_hash
from app.research.availability import AvailabilityClass, available_before, canonical_facts
from app.research.features import build_dataset as observed_dataset
from app.research.football_history import elo_context
from app.research.football_reconstruction import FEATURE_VERSION, build_dataset


def match(identity, at, home="A", away="B", goals=(2, 1), season=10):
    teams = {"A": 1, "B": 2, "C": 3, "D": 4}
    raw = {
        "id": identity,
        "league_id": 271,
        "season_id": season,
        "starting_at": at.isoformat(),
        "state": {"short_name": "FT"},
        "league": {"name": "Unit competition"},
        "participants": [
            {"id": teams[home], "name": home, "meta": {"location": "home"}},
            {"id": teams[away], "name": away, "meta": {"location": "away"}},
        ],
        "scores": [
            {"description": "CURRENT", "score": {"participant": side, "goals": score}}
            for side, score in zip(("home", "away"), goals, strict=True)
        ],
    }
    return {
        "event_id": identity,
        "artifact_id": f"artifact-{identity}",
        "provider": "sportmonks",
        "external_id": identity,
        "sport": "football",
        "start": at.isoformat(),
        "home": home,
        "away": away,
        "competition": "league",
        "surface": None,
        "home_score": goals[0],
        "away_score": goals[1],
        "outcome": 0 if goals[0] > goals[1] else 1 if goals[0] == goals[1] else 2,
        "available_at": "2027-01-01T00:00:00+00:00",
        "fetched_at": "2027-01-01T00:00:00+00:00",
        "run_id": "unit-test-only",
        "availability_basis": "FIRST_OBSERVED_FINAL",
        "raw": raw,
        "raw_hash": payload_hash(raw),
    }


def warmup(count=60):
    pairs = [("A", "B"), ("B", "A"), ("A", "C"), ("C", "A"), ("B", "C"), ("C", "B")]
    return [
        match(
            str(i),
            datetime(2025, 10, 1, tzinfo=UTC) + timedelta(days=i),
            *pairs[i % len(pairs)],
            goals=(i % 3, 1),
        )
        for i in range(count)
    ]


def regression_matches():
    return warmup() + [
        match("match-1", datetime(2026, 1, 1, tzinfo=UTC), "A", "B"),
        match("match-2", datetime(2026, 1, 8, tzinfo=UTC), "B", "C"),
        match("match-3", datetime(2026, 1, 15, tzinfo=UTC), "A", "C"),
    ]


def target_sample(rows, context=None):
    dataset = build_dataset(rows, 20, 10, context)
    return next(s for s in dataset["samples"] if s["event_id"] == "match-3")


def test_backfilled_result_is_usable_but_original_observed_version_is_unchanged():
    rows = regression_matches()
    result = target_sample(rows)
    assert {"artifact-match-1", "artifact-match-2"}.issubset(result["immutable_source_ids"])
    assert "artifact-match-3" not in result["source_ids"]
    assert result["latest_source_available_at"] < result["start"]
    assert observed_dataset(rows, 20, 10)["samples"] == []
    assert build_dataset(rows, 20, 10)["feature_version"] == FEATURE_VERSION


def test_target_and_future_result_never_change_pre_match_features():
    rows = regression_matches()
    before = target_sample(rows)
    changed = rows[:-1] + [match("match-3", datetime(2026, 1, 15, tzinfo=UTC), "A", "C", (0, 9))]
    after = target_sample(changed)
    assert before["features"] == after["features"]
    assert before["outcome"] != after["outcome"]
    for goals in ((8, 0), (0, 8)):
        future = match("match-4", datetime(2026, 2, 1, tzinfo=UTC), "A", "C", goals)
        assert target_sample(rows + [future])["features"] == before["features"]


def test_same_kickoff_and_completion_boundary_are_strict():
    rows = regression_matches()
    before = target_sample(rows)["features"]
    for goals in ((8, 0), (0, 8)):
        same = match("simultaneous", datetime(2026, 1, 15, tzinfo=UTC), "B", "D", goals)
        assert target_sample(rows + [same])["features"] == before
        boundary = match("boundary", datetime(2026, 1, 14, tzinfo=UTC), "B", "D", goals)
        assert target_sample(rows + [boundary])["features"] == before


def test_elo_uses_pre_bucket_state_and_updates_after_completion():
    at = datetime(2026, 1, 1, tzinfo=UTC)
    facts, _ = canonical_facts(
        [match("a", at), match("b", at, "B", "C"), match("t", at + timedelta(days=7), "A", "C")]
    )
    ratings, context = elo_context(facts[:-1], facts[-1])
    assert context["a"][:2] == (1500, 1500)
    assert context["b"][:2] == (1500, 1500)
    assert ratings["A"] > 1500
    assert ratings["C"] < 1500


def test_rolling_poisson_and_reconstructed_ledger_are_past_only():
    sample = target_sample(regression_matches())
    f = sample["features"]
    assert f["home_rolling_5"]["matches"] == 5
    assert (
        f["home_rolling_10"]["wins"]
        + f["home_rolling_10"]["draws"]
        + (f["home_rolling_10"]["losses"])
        == 10
    )
    assert f["home_goal_rate"] == pytest.approx(
        f["league_home_goals"] * f["home_attack_strength"] * f["away_defence_strength"]
    )
    ledger = f["home_reconstructed_ledger"]
    assert ledger["games_played"] == 41  # 40 warmup appearances and Jan 1, never Jan 15.
    assert ledger["rank"] is None and ledger["official_standing"] is False
    rows = regression_matches()
    rows[-1] = match("match-3", datetime(2026, 1, 15, tzinfo=UTC), "A", "C", season=11)
    assert target_sample(rows)["features"]["home_reconstructed_ledger"] is None


def test_mutable_context_is_not_backdated_and_provenance_is_preserved():
    rows = regression_matches()
    context = [
        {
            "event_id": "match-3",
            "snapshot_id": side,
            "kind": "football_team",
            "side": side,
            "source_provider": "sportmonks",
            "observed_at": "2027-01-01T00:00:00+00:00",
            "fetched_at": "2027-01-01T00:00:00+00:00",
            "post_match": False,
            "sample_size": 20,
            "goals_per_match": 2,
            "standing_points": 30,
        }
        for side in ("home", "away")
    ]
    assert target_sample(rows, context)["context_source_ids"] == []
    for row in context:
        row.update(observed_at="2026-01-14T00:00:00+00:00", fetched_at="2026-01-14T00:00:00+00:00")
    sample = target_sample(rows, context)
    assert sample["context_source_ids"] == ["home", "away"]
    assert len(sample["context_provenance"]) == 2
    for row in context:
        row["source_updated_at"] = "2026-01-15T00:00:00+00:00"
    assert target_sample(rows, context)["context_source_ids"] == []


def test_backfill_order_rebuild_and_duplicate_versions_are_deterministic():
    rows = regression_matches()
    first = build_dataset(rows, 20, 10)
    assert first == build_dataset(list(reversed(rows)), 20, 10)
    assert first == build_dataset(rows, 20, 10)
    duplicate = deepcopy(rows[0])
    duplicate["artifact_id"] = "zzz-second-version"
    duplicate["raw"]["statistics"] = [{"a_mutable_snapshot": 999}]
    duplicate["raw_hash"] = payload_hash(duplicate["raw"])
    assert first == build_dataset(rows + [duplicate], 20, 10)


def test_conflicting_results_and_bad_provenance_fail_closed():
    rows = regression_matches()
    conflict = match("match-1", datetime(2026, 1, 1, tzinfo=UTC), "A", "B", (0, 9))
    facts, bad = canonical_facts(rows + [conflict])
    assert bad["match-1"] == "conflicting_immutable_versions"
    assert all(f.event_id != "match-1" for f in facts)
    broken = deepcopy(rows[0])
    broken["raw_hash"] = "wrong"
    assert canonical_facts([broken])[1][broken["event_id"]] == "missing_provenance"


def test_original_thresholds_and_warmup_remain_enforced():
    rows = warmup(240)
    result = build_dataset(rows, 200, 10)
    assert result["samples"]
    assert all(len(s["immutable_source_ids"]) >= 200 for s in result["samples"])
    unseen = match("unseen", datetime(2026, 9, 1, tzinfo=UTC), "A", "D")
    result = build_dataset(rows + [unseen], 200, 10)
    assert result["exclusions"]["insufficient_participant_history"] == 1
    assert result["exclusions"]["no_prior_matches"] == 2  # 24h strict boundary.
    assert result["minimum_history"] == 200 and result["minimum_participant"] == 10


def test_no_xg_and_snapshot_policy_never_accepts_event_fact_dict():
    sample = target_sample(regression_matches())
    assert sample["features"]["xg"] is None
    assert not build_dataset(regression_matches(), 20, 10)["xg_available"]
    assert not available_before({}, datetime.now(UTC), AvailabilityClass.IMMUTABLE_EVENT_TIME)
    assert not available_before({}, datetime.now(UTC), AvailabilityClass.OBSERVED_SNAPSHOT_TIME)


@pytest.mark.parametrize(
    "mutation",
    [
        {"available_at": "2025-01-01T00:00:00+00:00"},
        {"start": "not-a-time"},
    ],
)
def test_ambiguous_event_time_is_rejected(mutation):
    row = regression_matches()[0]
    row.update(mutation)
    facts, rejected = canonical_facts([row])
    assert not facts and rejected


def test_earlier_observed_final_and_24h_fallback_boundaries():
    at = datetime(2026, 3, 1, tzinfo=UTC)
    row = match("march", at)
    fact = canonical_facts([row])[0][0]
    policy = AvailabilityClass.IMMUTABLE_EVENT_TIME
    assert not available_before(fact, at + timedelta(hours=23), policy)
    assert not available_before(fact, at + timedelta(hours=24), policy)
    assert available_before(fact, at + timedelta(hours=24, seconds=1), policy)
    row["available_at"] = row["fetched_at"] = (at + timedelta(hours=3)).isoformat()
    observed = canonical_facts([row])[0][0]
    assert observed.completion_basis == "OBSERVED_FINAL_UPPER_BOUND"
    assert not available_before(observed, at + timedelta(hours=3), policy)
    assert available_before(observed, at + timedelta(hours=3, seconds=1), policy)


def test_duplicate_provider_fixture_across_database_ids_is_excluded():
    row = regression_matches()[0]
    duplicate = {**row, "event_id": "different-db-id"}
    facts, bad = canonical_facts([row, duplicate])
    assert not facts
    assert bad == {
        row["event_id"]: "conflicting_event_identity",
        "different-db-id": "conflicting_event_identity",
    }


def test_database_identity_order_cannot_change_feature_values():
    rows = regression_matches()
    expected = {r["event_id"]: r["features"] for r in build_dataset(rows, 20, 10)["samples"]}
    changed = deepcopy(rows)
    ids = {row["event_id"]: f"db-{1000 - i}" for i, row in enumerate(changed)}
    for row in changed:
        row["event_id"] = ids[row["event_id"]]
    actual = {r["event_id"]: r["features"] for r in build_dataset(changed, 20, 10)["samples"]}
    assert all(actual[ids[identity]] == value for identity, value in expected.items())


def test_venue_form_excludes_opposite_venue_roles():
    rows = regression_matches()
    result = target_sample(rows)["features"]
    # Venue-only window: two warmup 2:1 wins, two 0:1 losses and the Jan 1 2:1 win.
    assert result["home_venue_form"]["wins"] == 3
    assert result["home_venue_form"]["losses"] == 2
    assert result["home_venue_form"]["goals_for"] == pytest.approx(1.2)
    assert result["home_venue_form"]["matches"] == 5
