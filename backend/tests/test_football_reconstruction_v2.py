"""Synthetic unit fixtures only. Production history is never synthesized."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_football_reconstruction import match, regression_matches, warmup

from app.research.availability import canonical_facts, prior_facts
from app.research.football_audit_v2 import audit
from app.research.football_history import elo_context
from app.research.football_policy_v2 import coverage, family_coverage, windows
from app.research.football_reconstruction import build_dataset as v1
from app.research.football_reconstruction_v2 import FEATURE_VERSION, build_dataset, sample


def facts_for(rows):
    facts, rejected = canonical_facts(rows)
    assert not rejected
    target = next(f for f in facts if f.event_id == "match-3")
    return target, prior_facts(facts, target)


def early_season():
    target, prior = facts_for(regression_matches())
    return replace(target, season="11"), [
        replace(f, season="11") if f.event_id.startswith("match-") else f for f in prior
    ]


def test_early_season_never_fills_result_goal_or_venue_windows():
    target, prior = early_season()
    groups = windows(target, prior)
    for side in ("home", "away"):
        for family in ("rolling_5", "rolling_10", "venue", "poisson", "season"):
            assert all(f.season == "11" for f in groups[f"{side}_{family}"])
            assert len(groups[f"{side}_{family}"]) < 5
    assert all(f.season == "11" for f in groups["poisson_baseline"])
    assert not family_coverage(groups)["poisson_inputs"]
    counts = coverage(target, groups)
    assert counts["home"]["long_term_history_count"] > 10
    assert counts["home"]["current_season_matches"] == 1
    assert not counts["home"]["rolling_10_complete"]
    assert sample(target, prior, [])[1] == "insufficient_current_season_home_away_or_league_history"


def test_elo_survives_season_but_is_separate_for_a_new_competition():
    target, prior = early_season()
    groups = windows(target, prior)
    ratings, _ = elo_context(groups["elo"], target)
    assert ratings[target.home] != 1500
    moved = replace(target, competition="new-league", league="501")
    moved_groups = windows(moved, prior)
    moved_ratings, _ = elo_context(moved_groups["elo"], moved)
    assert moved_ratings[moved.home] == 1500
    assert all(not rows for family, rows in moved_groups.items() if family != "long_term_history")


@pytest.mark.parametrize("change", ["competition", "season"])
def test_poisson_and_short_form_are_invariant_to_out_of_scope_goals(change):
    target, prior = facts_for(regression_matches())
    other = [
        replace(
            f,
            event_id="other-" + f.event_id,
            artifact_id="other-" + f.artifact_id,
            external_id="other-" + f.external_id,
            **(
                {"competition": "cup", "league": "999"}
                if change == "competition"
                else {"season": "old"}
            ),
        )
        for f in prior
    ]
    before, _ = sample(target, prior + other, [])
    after, _ = sample(target, prior + [replace(f, home_score=25, away_score=0) for f in other], [])
    assert before is not None and after is not None
    for key, value in before["features"].items():
        if "elo" not in key and "opponent" not in key:
            assert after["features"][key] == value
    for family, ids in before["family_source_ids"].items():
        if family not in {"elo", "long_term_history"}:
            assert all(not i.startswith("other-") for i in ids)


def test_ledger_opponent_strength_and_form_use_correct_context():
    target, prior = facts_for(regression_matches())
    row, reason = sample(target, prior, [])
    assert reason is None
    groups = windows(target, prior)
    _, adjustments = elo_context(groups["elo"], target)
    expected = (
        sum(
            adjustments[f.event_id][2] * (1 if f.home == target.home else -1)
            for f in groups["home_rolling_10"]
        )
        / 10
    )
    assert row["features"]["home_opponent_adjusted_form"] == pytest.approx(expected)
    assert row["features"]["home_reconstructed_ledger"]["games_played"] == 41
    assert row["features"]["home_reconstructed_ledger"]["rank"] is None
    assert row["features"]["home_reconstructed_ledger"]["official_standing"] is False


def test_v1_unchanged_and_v2_deterministic_and_auditable():
    rows = regression_matches()
    before = v1(rows, 20, 10)
    result = build_dataset(rows, 20, 10)
    assert result["feature_version"] == FEATURE_VERSION
    assert result == build_dataset(rows[::-1], 20, 10)
    assert before == v1(rows, 20, 10)
    assert before["feature_version"] == "strict-historical-reconstruction-v1"
    checked = audit(result, rows)
    assert checked["status"] == "PASSED" and not checked["violations"]
    assert checked["cross_season_short_form_contamination"] == 0


def test_same_kickoff_future_and_completion_boundary():
    rows = regression_matches()
    target, prior = facts_for(rows)
    baseline, _ = sample(target, prior, [])
    for kickoff in (target.kickoff, datetime(2026, 2, 1, tzinfo=UTC)):
        future = replace(prior[0], event_id="future", kickoff=kickoff, home_score=20)
        assert sample(target, prior + [future], [])[0] == baseline
    boundary = replace(prior[0], event_id="boundary", completed_bound=target.kickoff)
    assert sample(target, prior + [boundary], [])[0] == baseline


def test_snapshot_time_and_scope_gates_and_provenance():
    target, prior = facts_for(regression_matches())
    context = [
        dict(
            event_id=target.event_id,
            snapshot_id=side,
            side=side,
            kind="football_team",
            source_provider="sportmonks",
            league=target.league,
            season=target.season,
            observed_at="2026-01-14T00:00:00+00:00",
            fetched_at="2026-01-14T00:00:00+00:00",
            post_match=False,
            sample_size=20,
            goals_per_match=2,
            standing_points=30,
        )
        for side in ("home", "away")
    ]
    row, _ = sample(target, prior, context)
    assert sorted(row["context_provenance"], key=lambda r: r["side"]) == sorted(
        context, key=lambda r: r["side"]
    )
    assert row["context_source_ids"] == ["home", "away"]
    for field, value in (
        ("season", "old"),
        ("league", "cup"),
        ("post_match", True),
        ("source_updated_at", target.kickoff.isoformat()),
        ("observed_at", "2027-01-01T00:00:00+00:00"),
    ):
        bad = [dict(r, **{field: value}) for r in context]
        assert sample(target, prior, bad)[0]["context_source_ids"] == []
    assert sample(target, prior, context)[0]["features"]["xg"] is None


def test_global_and_participant_gates_not_lowered():
    result = build_dataset(warmup(240), 200, 10)
    assert result["minimum_history"] == 200 and result["minimum_participant"] == 10
    assert all(
        s["coverage"][side]["long_term_history_count"] >= 10
        for s in result["samples"]
        for side in ("home", "away")
    )
    assert all(
        e["available_history"] >= 200
        for e in result["event_evidence"]
        if not e["first_failed_gate"]
    )


def test_audit_detects_tampering_and_duplicate_targets():
    rows = regression_matches()
    result = deepcopy(build_dataset(rows, 20, 10))
    result["samples"][0]["features"]["home_goal_rate"] = 99
    result["samples"].append(result["samples"][0])
    checked = audit(result, rows)
    assert checked["status"] == "FAILED" and checked["duplicate_count"] == 1
    assert checked["violations"]


def test_long_winter_gap_is_diagnosed_not_arbitrarily_cut_off():
    rows = warmup() + [match("match-3", datetime(2026, 3, 15, tzinfo=UTC), "A", "C")]
    target, prior = facts_for(rows)
    row, _ = sample(target, prior, [])
    assert row is not None
    assert row["coverage"]["home"]["recent_form_oldest_age_days"] > 90


def test_partial_current_season_windows_do_not_require_ten_matches():
    current = [
        match(
            f"current-{i}",
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            *(("A", "B") if i < 3 else ("B", "C") if i < 6 else ("B", "D")),
            season=11,
        )
        for i in range(20)
    ]
    rows = (
        warmup()
        + current
        + [match("match-3", datetime(2026, 2, 1, tzinfo=UTC), "A", "C", season=11)]
    )
    target, prior = facts_for(rows)
    row, reason = sample(target, prior, [])
    assert reason is None and row is not None
    for side in ("home", "away"):
        assert row["features"][f"{side}_rolling_5"]["matches"] == 3
        assert row["features"][f"{side}_rolling_10"]["matches"] == 3
        assert not row["coverage"][side]["rolling_5_complete"]
        assert row["features"][f"{side}_reconstructed_ledger"]["games_played"] == 3
