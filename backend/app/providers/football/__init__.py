"""Football adapters plug into the FootballProvider contract."""

from app.providers.football.api_football import ApiFootballProvider
from app.providers.football.sportmonks import SportmonksFootballProvider

__all__ = ["ApiFootballProvider", "SportmonksFootballProvider"]
