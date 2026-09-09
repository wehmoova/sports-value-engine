"""Football-only reconstruction policy. Never rewrite persisted observation times."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from app.providers.odds.the_odds_api import payload_hash
from app.research.features import context_available_at, timestamp
from app.services.football_sync import normalize_football_fixture

CONSERVATIVE_DURATION_HOURS = 24


class AvailabilityClass(StrEnum):
    IMMUTABLE_EVENT_TIME = "IMMUTABLE_EVENT_TIME"
    OBSERVED_SNAPSHOT_TIME = "OBSERVED_SNAPSHOT_TIME"


@dataclass(frozen=True)
class MatchFact:
    event_id: str
    artifact_id: str
    external_id: str
    competition: str
    season: str
    league: str
    home: str
    away: str
    kickoff: datetime
    completed_bound: datetime
    completion_basis: str
    home_score: int
    away_score: int
    observed_at: str
    raw_hash: str

    @property
    def outcome(self) -> int:
        return (
            0
            if self.home_score > self.away_score
            else (1 if self.home_score == self.away_score else 2)
        )


def available_before(
    source: MatchFact | dict[str, Any],
    at: datetime,
    policy: AvailabilityClass,
) -> bool:
    if policy == AvailabilityClass.IMMUTABLE_EVENT_TIME:
        if not isinstance(source, MatchFact):
            return False
        return source.kickoff < at and source.completed_bound < at
    if not isinstance(source, dict) or source.get("post_match"):
        return False
    try:
        return context_available_at(source) < at
    except (KeyError, TypeError, ValueError):
        return False


def _fact(row: dict[str, Any]) -> MatchFact:
    if row.get("sport") != "football" or row.get("provider") != "sportmonks":
        raise ValueError("unsupported_provider")
    raw = row["raw"]
    if not isinstance(raw, dict):
        raise ValueError("invalid_event_fact")
    if (
        row.get("availability_basis") != "FIRST_OBSERVED_FINAL"
        or not row.get("run_id")
        or not row.get("artifact_id")
        or not row.get("event_id")
        or payload_hash(raw) != row.get("raw_hash")
    ):
        raise ValueError("missing_provenance")
    normalized = normalize_football_fixture(raw, "sportmonks")
    start = timestamp(row["start"])
    observed = timestamp(row["available_at"])
    fetched = timestamp(row["fetched_at"])
    if normalized.status != "FINAL":
        raise ValueError("not_final")
    if start != normalized.start_time or observed <= start or fetched < observed:
        raise ValueError("ambiguous_event_time")
    if str(normalized.external_id) != str(row["external_id"]):
        raise ValueError("conflicting_event_identity")
    if not row.get("competition") or not raw.get("season_id") or not raw.get("league_id"):
        raise ValueError("missing_competition_or_season")
    home, away = row["home"], row["away"]
    if (
        not home
        or not away
        or home == away
        or not normalized.home_external_id
        or not normalized.away_external_id
        or (normalized.home_external_id == normalized.away_external_id)
    ):
        raise ValueError("conflicting_event_identity")
    for value, verified in (
        (row["home_score"], normalized.home_score),
        (row["away_score"], normalized.away_score),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 30
            or int(value) != value
            or value != verified
        ):
            raise ValueError("invalid_final_score")
    bound = start + timedelta(hours=CONSERVATIVE_DURATION_HOURS)
    completion = min(bound, observed)
    fact = MatchFact(
        str(row["event_id"]),
        str(row["artifact_id"]),
        str(row["external_id"]),
        str(row["competition"]),
        str(raw["season_id"]),
        str(raw["league_id"]),
        str(home),
        str(away),
        start,
        completion,
        "OBSERVED_FINAL_UPPER_BOUND" if observed <= bound else "FINAL_KICKOFF_PLUS_24H",
        int(row["home_score"]),
        int(row["away_score"]),
        row["available_at"],
        row["raw_hash"],
    )
    if row["outcome"] != fact.outcome:
        raise ValueError("invalid_final_score")
    return fact


def canonical_facts(
    rows: list[dict[str, Any]],
) -> tuple[list[MatchFact], dict[str, str]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    provider_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        groups[str(row.get("event_id", "missing"))].append(row)
        provider_ids[(str(row.get("provider")), str(row.get("external_id")))].add(
            str(row.get("event_id", "missing"))
        )
    facts = []
    rejected = {}
    for event_id, versions in sorted(groups.items()):
        try:
            if any(
                len(provider_ids[(str(r.get("provider")), str(r.get("external_id")))]) > 1
                for r in versions
            ):
                raise ValueError("conflicting_event_identity")
            candidates = [_fact(row) for row in versions]
            signatures = {
                (
                    f.external_id,
                    f.competition,
                    f.season,
                    f.league,
                    f.home,
                    f.away,
                    f.kickoff,
                    f.home_score,
                    f.away_score,
                )
                for f in candidates
            }
            if len(signatures) != 1:
                raise ValueError("conflicting_immutable_versions")
            facts.append(
                min(candidates, key=lambda f: (f.completed_bound, f.observed_at, f.artifact_id))
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            known = {
                "unsupported_provider",
                "missing_provenance",
                "not_final",
                "ambiguous_event_time",
                "conflicting_event_identity",
                "missing_competition_or_season",
                "invalid_final_score",
                "conflicting_immutable_versions",
            }
            rejected[event_id] = str(exc) if str(exc) in known else "invalid_event_fact"
    return sorted(facts, key=lambda f: (f.kickoff, f.external_id)), rejected


def prior_facts(facts: list[MatchFact], target: MatchFact) -> list[MatchFact]:
    return [
        f
        for f in facts
        if f.event_id != target.event_id
        and available_before(f, target.kickoff, AvailabilityClass.IMMUTABLE_EVENT_TIME)
    ]
