"""API integration tests using TestClient."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_players(provider: str = "mock", model: str = "mock-default"):
    return [
        {
            "player_id": i,
            "model_config": {
                "provider_id": provider,
                "model_id": model,
            },
        }
        for i in range(1, 13)
    ]


class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestProviders:
    def test_list_providers(self):
        r = client.get("/api/providers")
        assert r.status_code == 200
        data = r.json()
        ids = {p["id"] for p in data}
        assert "mock" in ids


class TestSetupValidation:
    def test_valid_mock_setup(self):
        r = client.post("/api/setup/validate", json={"players": _make_players()})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True

    def test_invalid_provider(self):
        players = _make_players("unknown", "x")
        r = client.post("/api/setup/validate", json={"players": players})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert any("UNKNOWN_PROVIDER" in e["code"] for e in body["errors"])


class TestGameLifecycle:
    def test_create_and_start(self):
        r = client.post("/api/games", json={"players": _make_players()})
        assert r.status_code == 200
        gid = r.json()["game_id"]

        r = client.post(f"/api/games/{gid}/start")
        assert r.status_code == 200
        assert r.json()["status"] == "started"

    def test_get_game(self):
        r = client.post("/api/games", json={"players": _make_players()})
        gid = r.json()["game_id"]
        r = client.get(f"/api/games/{gid}")
        assert r.status_code == 200
        body = r.json()
        assert body["game_id"] == gid
        assert body["phase"] == "setup"

    def test_events_and_log(self):
        r = client.post("/api/games", json={"players": _make_players()})
        gid = r.json()["game_id"]

        # step a few times
        for _ in range(5):
            r = client.post(f"/api/games/{gid}/step")
            assert r.status_code == 200

        r = client.get(f"/api/games/{gid}/events?after_id=0")
        assert r.status_code == 200
        events = r.json()
        assert len(events) > 0

        r = client.get(f"/api/games/{gid}/log")
        assert r.status_code == 200
        log = r.json()
        assert len(log) >= len(events)

    def test_step_to_completion(self):
        r = client.post("/api/games", json={"players": _make_players()})
        gid = r.json()["game_id"]

        ended = False
        for _ in range(200):  # safety limit
            r = client.post(f"/api/games/{gid}/step")
            assert r.status_code == 200
            if r.json()["ended"]:
                ended = True
                break

        assert ended
        r = client.get(f"/api/games/{gid}")
        assert r.json()["phase"] == "game_end"
