from dataclasses import dataclass, field


@dataclass
class TennisElo:
    overall: float = 1500.0
    surfaces: dict[str, float] = field(default_factory=dict)
    surface_matches: dict[str, int] = field(default_factory=dict)
    k_factor: float = 32.0

    def rating_for(self, surface: str) -> float:
        surface_rating = self.surfaces.get(surface.lower(), self.overall)
        matches = self.surface_matches.get(surface.lower(), 0)
        surface_weight = matches / (matches + 8)
        shrunk_surface = surface_weight * surface_rating + (1 - surface_weight) * self.overall
        return 0.35 * self.overall + 0.65 * shrunk_surface

    def expected(self, opponent: "TennisElo", surface: str) -> float:
        difference = opponent.rating_for(surface) - self.rating_for(surface)
        return 1 / (1 + 10 ** (difference / 400))

    def update(self, opponent: "TennisElo", surface: str, won: bool) -> None:
        expected = self.expected(opponent, surface)
        adjustment = self.k_factor * ((1.0 if won else 0.0) - expected)
        previous_overall = self.overall
        self.overall += adjustment * 0.35
        key = surface.lower()
        self.surfaces[key] = self.surfaces.get(key, previous_overall) + adjustment * 0.65
        self.surface_matches[key] = self.surface_matches.get(key, 0) + 1
