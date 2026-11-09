"""Tests for the FastAPI daemon scoring endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rootguard.daemon import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_score_safe():
    client = TestClient(app)
    response = client.post(
        "/score",
        json={
            "user_request": "list files",
            "proposed_action": "ls -la",
            "source": "user_direct",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] in {"allow", "confirm", "block"}
    assert 0.0 <= body["risk_score"] <= 1.0


def test_score_malformed_blocked():
    client = TestClient(app)
    response = client.post(
        "/score",
        json={
            "user_request": "",
            "proposed_action": "ls",
            "source": "user_direct",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "block"


def test_score_invalid_source_blocked():
    client = TestClient(app)
    response = client.post(
        "/score",
        json={
            "user_request": "list files",
            "proposed_action": "ls",
            "source": "not-a-source",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "block"


def test_score_dangerous_user_direct_blocked():
    client = TestClient(app)
    response = client.post(
        "/score",
        json={
            "user_request": "delete everything",
            "proposed_action": "rm -rf /",
            "source": "user_direct",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "block"
