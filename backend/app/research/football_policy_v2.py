"""V2 context windows. Counts describe known results, not complete provider coverage."""

from collections import Counter
from typing import Any

from app.research.availability import MatchFact, prior_facts

# Keep the existing Poisson coverage and shrinkage assumptions. Rolling windows are
# explicitly 'up to N', not imputed full windows; missingness is never filled.
MINIMUMS = {"rolling": 1, "venue_poisson": 3, "league_poisson": 20}


def windows(target: MatchFact, facts: list[MatchFact]) -> dict[str, list[MatchFact]]:
    prior = prior_facts(facts, target)
    competition = [
        f for f in prior if (f.competition, f.league) == (target.competition, target.league)
    ]
    season = [f for f in competition if f.season == target.season]
    result = {"long_term_history": prior, "elo": competition, "poisson_baseline": season}
    for side, team in (("home", target.home), ("away", target.away)):
        rows = [f for f in season if team in (f.home, f.away)]
        venue = [f for f in rows if getattr(f, side) == team]
        result[f"{side}_season"] = rows
        result[f"{side}_rolling_5"] = rows[-5:]
        result[f"{side}_rolling_10"] = rows[-10:]
        result[f"{side}_venue"] = venue[-5:]
        result[f"{side}_poisson"] = venue[-20:]
    return result


def coverage(target: MatchFact, groups: dict[str, list[MatchFact]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for side, team in (("home", target.home), ("away", target.away)):
        long_term = [f for f in groups["long_term_history"] if team in (f.home, f.away)]
        current = groups[f"{side}_season"]
        recent = groups[f"{side}_rolling_10"]
        result[side] = {
            "long_term_history_count": len(long_term),
            "competition_history_count": sum(team in (f.home, f.away) for f in groups["elo"]),
            "current_season_matches": len(current),
            "current_season_home_matches": sum(f.home == team for f in current),
            "current_season_away_matches": sum(f.away == team for f in current),
            "poisson_history_count": len(groups[f"{side}_poisson"]),
            "poisson_league_history_count": len(groups["poisson_baseline"]),
            "poisson_oldest_used_match_age_days": age(target, groups[f"{side}_poisson"]),
            "rolling_windows": {
                str(n): {"requested_window": n, "available_valid_matches": min(n, len(current))}
                for n in (5, 10)
            },
            "rolling_5_complete": len(current) >= 5,
            "rolling_10_complete": len(current) >= 10,
            "days_since_previous_match": age(target, long_term[-1:]),
            "days_since_previous_season_match": age(target, current[-1:]),
            "recent_form_oldest_age_days": age(target, recent),
            "goal_form_oldest_age_days": age(target, recent),
            "venue_form_oldest_age_days": age(target, groups[f"{side}_venue"]),
            "largest_within_season_gap_days": max(
                (
                    (b.kickoff - a.kickoff).total_seconds() / 86400
                    for a, b in zip(current, current[1:], strict=False)
                ),
                default=None,
            ),
        }
    return result


def age(target: MatchFact, rows: list[MatchFact]) -> float | None:
    return (target.kickoff - rows[0].kickoff).total_seconds() / 86400 if rows else None


def family_coverage(groups: dict[str, list[MatchFact]]) -> dict[str, bool]:
    form = min(len(groups[f"{s}_season"]) for s in ("home", "away")) >= MINIMUMS["rolling"]
    venue = min(len(groups[f"{s}_venue"]) for s in ("home", "away")) >= MINIMUMS["rolling"]
    poisson = (
        min(len(groups[f"{s}_poisson"]) for s in ("home", "away")) >= MINIMUMS["venue_poisson"]
        and len(groups["poisson_baseline"]) >= MINIMUMS["league_poisson"]
    )
    return {
        "elo": True,  # Explicit competition-mean prior is defined even for newcomers.
        "recent_form": form,
        "goal_form": form,
        "home_away_form": venue,
        "opponent_adjusted_form": form,
        "poisson_inputs": poisson,
        "reconstructed_season_state": form,
        "complete_last_5": all(len(groups[f"{s}_season"]) >= 5 for s in ("home", "away")),
        "complete_last_10": all(len(groups[f"{s}_season"]) >= 10 for s in ("home", "away")),
    }


def history_distributions(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        field: dict(
            sorted(
                Counter(
                    str(row["coverage"][side][field])
                    for row in evidence
                    for side in ("home", "away")
                ).items()
            )
        )
        for field in (
            "long_term_history_count",
            "competition_history_count",
            "current_season_matches",
            "current_season_home_matches",
            "current_season_away_matches",
            "poisson_history_count",
            "poisson_league_history_count",
        )
    }


def segment_summary(facts: list[MatchFact], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for league, season in sorted({(f.league, f.season) for f in facts}):
        matches = [f for f in facts if (f.league, f.season) == (league, season)]
        rows = [r for r in evidence if (r["league"], r["season"]) == (league, season)]
        participants = Counter(team for f in matches for team in (f.home, f.away))
        families: Counter[str] = Counter()
        for row in rows:
            families.update({k: int(v) for k, v in row["families"].items()})
        result[f"{league}:{season}"] = {
            "final_fixtures": len(matches),
            "teams": len(participants),
            "matches_per_team": dict(Counter(str(n) for n in participants.values())),
            "eligible_samples": sum(r["first_failed_gate"] is None for r in rows),
            "feature_coverage": dict(families),
            "history_distributions": history_distributions(rows),
        }
    return result
