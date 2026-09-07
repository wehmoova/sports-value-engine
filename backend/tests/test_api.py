from fastapi.testclient import TestClient

from app.main import app


def test_health_and_dashboard_contract() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        payload = dashboard.json()
        assert "metrics" in payload
        assert "top_picks" in payload


def test_challenge_validation() -> None:
    with TestClient(app) as client:
        invalid = client.post(
            "/api/v1/challenge/simulate",
            json={"starting_bankroll": 100, "target_bankroll": 10, "days": 7},
        )
        assert invalid.status_code == 422
