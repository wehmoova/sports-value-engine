"""Shared real-provider page retrieval for dry-run and durable ingestion."""

import asyncio
from datetime import date
from typing import Any

from app.core.config import settings
from app.providers.football.sportmonks import SportmonksFootballProvider
from app.providers.odds.the_odds_api import ProviderError
from app.services.football_sync import normalize_football_fixture


async def football_page(
    provider: SportmonksFootballProvider,
    start: date,
    end: date,
    league: int,
    page: int,
) -> tuple[list[dict[str, Any]], bool]:
    await asyncio.sleep(settings.backfill_request_delay_seconds)
    path = f"fixtures/between/{start}/{end}"
    params = {
        "filters": f"fixtureLeagues:{league}",
        "page": str(page),
        "include": "participants;league;state;scores;statistics.type",
    }
    try:
        raw = await provider._request(path, params)
    except PermissionError:
        if provider.last_status_code != 403:
            raise
        params["include"] = "participants;league;state;scores"
        raw = await provider._request(path, params)
    rows = provider._records(raw)
    if any(int(r.get("league_id", -1)) != league for r in rows):
        raise ProviderError("Provider returned unexpected league")
    for row in rows:
        # Verify provider range without accepting a guessed kickoff.
        normalized = normalize_football_fixture(row, "sportmonks")
        if not start <= normalized.start_time.date() <= end:
            raise ProviderError("Provider returned fixture outside requested range")
    return rows, bool(provider.last_pagination.get("has_more"))


async def preview(
    provider: SportmonksFootballProvider,
    windows: list[tuple[date, date]],
    leagues: list[int],
    season: int | None,
    max_pages: int,
) -> dict[str, Any]:
    """No database access, checkpoints or fabricated historical availability."""
    pages = received = final = statistics = duplicates = 0
    seen: set[str] = set()
    seasons: set[int] = set()
    for start, end in windows:
        for league in leagues:
            page = 1
            while True:
                if pages >= max_pages:
                    return {
                        "status": "DRY_RUN",
                        "complete": False,
                        **summary(pages, received, final, statistics, duplicates, seasons),
                    }
                rows, more = await football_page(provider, start, end, league, page)
                pages += 1
                for row in rows:
                    if season is not None and row.get("season_id") != season:
                        continue
                    identity = str(row["id"])
                    if identity in seen:
                        duplicates += 1
                        continue
                    seen.add(identity)
                    received += 1
                    if row.get("season_id"):
                        seasons.add(int(row["season_id"]))
                    event = normalize_football_fixture(row, "sportmonks")
                    if (
                        event.status == "FINAL"
                        and event.home_score is not None
                        and event.away_score is not None
                    ):
                        final += 1
                        statistics += int(bool(row.get("statistics")))
                if not more:
                    break
                page += 1
                if page > 1000:
                    raise ProviderError("Pagination safety bound exceeded")
    return {
        "status": "DRY_RUN",
        "complete": True,
        **summary(pages, received, final, statistics, duplicates, seasons),
    }


def summary(
    pages: int, received: int, final: int, statistics: int, duplicates: int, seasons: set[int]
) -> dict[str, Any]:
    return {
        "pages": pages,
        "fixtures": received,
        "final_results": final,
        "final_fixtures_with_statistics": statistics,
        "duplicate_provider_ids": duplicates,
        "seasons_observed": sorted(seasons),
        "pre_match_context_proofs": 0,
        "new_immediate_point_in_time_samples": 0,
        "availability_basis": "FIRST_OBSERVED_FINAL",
        "note": "Fetched now: eligible as history only for later kickoffs. No backdating.",
        "xg_available": False,
        "database_writes": 0,
    }
