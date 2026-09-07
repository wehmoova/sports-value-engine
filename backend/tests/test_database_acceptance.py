import pytest

from app.scripts.verify_database import acceptance_checks


def populated_counts() -> dict[str, int]:
    return dict(
        events=1, odds_snapshots=1, football_statistics=1, tennis_statistics=1, mock_events=0
    )


def test_real_postgresql_bootstrap_passes() -> None:
    assert all(acceptance_checks("postgresql", populated_counts()).values())


@pytest.mark.parametrize(
    "missing", ["events", "odds_snapshots", "football_statistics", "tennis_statistics"]
)
def test_missing_data_fails(missing: str) -> None:
    counts = populated_counts()
    counts[missing] = 0
    assert not all(acceptance_checks("postgresql", counts).values())


def test_sqlite_and_mock_data_cannot_certify_postgresql() -> None:
    counts = populated_counts()
    assert not all(acceptance_checks("sqlite", counts).values())
    counts["mock_events"] = 1
    assert not all(acceptance_checks("postgresql", counts).values())
    assert not all(acceptance_checks("postgresql", {}).values())
