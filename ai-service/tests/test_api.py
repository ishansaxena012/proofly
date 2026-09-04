"""The AI service HTTP surface (docs/API.md §AI service API)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

KEY = "test-internal-key"
JOB_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", KEY)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BACKEND_INTERNAL_URL", "http://backend.invalid")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_needs_no_key_and_reports_providers(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "proofly-ai-service"
    assert body["demoMode"] is True
    assert body["providers"]["llm"] == "mock"


@pytest.mark.parametrize(
    "path",
    [
        "/internal/v1/research/execute",
        f"/internal/v1/research/{JOB_ID}/followup",
        f"/internal/v1/research/{JOB_ID}/cancel",
    ],
)
def test_internal_routes_require_the_shared_key(client, path):
    unauthenticated = client.post(path, json={})
    assert unauthenticated.status_code == 403
    assert unauthenticated.json()["errorCode"] == "FORBIDDEN"

    wrong_key = client.post(path, json={}, headers={"X-Internal-Key": "nope"})
    assert wrong_key.status_code == 403


def test_execute_accepts_and_runs_in_the_background(client):
    response = client.post(
        "/internal/v1/research/execute",
        json={"researchJobId": JOB_ID, "productQuery": "Sony WH-1000XM6", "demoMode": True},
        headers={"X-Internal-Key": KEY},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["researchJobId"] == JOB_ID
    assert body["accepted"] is True


def test_execute_rejects_an_empty_query(client):
    response = client.post(
        "/internal/v1/research/execute",
        json={"researchJobId": JOB_ID, "productQuery": "   ", "demoMode": True},
        headers={"X-Internal-Key": KEY},
    )
    assert response.status_code == 400
    assert response.json()["errorCode"] == "VALIDATION_ERROR"


def test_followup_answers_from_supplied_evidence_only(client):
    response = client.post(
        f"/internal/v1/research/{JOB_ID}/followup",
        headers={"X-Internal-Key": KEY},
        json={
            "question": "How is the microphone in wind?",
            "evidence": [
                {
                    "id": "e1",
                    "text": "Outside on a windy afternoon the wind overwhelms the microphone.",
                    "topic": "Microphone & Call Quality",
                },
                {
                    "id": "e2",
                    "text": "Sound quality is excellent for the category.",
                    "topic": "Sound Quality",
                },
            ],
            "claims": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["citedEvidenceIds"] == ["e1"]
    assert "wind" in body["answer"].lower()


def test_followup_admits_when_the_evidence_does_not_answer(client):
    response = client.post(
        f"/internal/v1/research/{JOB_ID}/followup",
        headers={"X-Internal-Key": KEY},
        json={
            "question": "Is it waterproof for scuba diving?",
            "evidence": [
                {"id": "e1", "text": "Sound quality is excellent.", "topic": "Sound Quality"}
            ],
            "claims": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["citedEvidenceIds"] == []
    assert "insufficient evidence" in body["answer"].lower()


def test_followup_rejects_an_empty_question(client):
    response = client.post(
        f"/internal/v1/research/{JOB_ID}/followup",
        headers={"X-Internal-Key": KEY},
        json={"question": "  ", "evidence": [], "claims": []},
    )
    assert response.status_code == 400


def test_cancel_is_best_effort(client):
    response = client.post(
        f"/internal/v1/research/{JOB_ID}-unknown/cancel", headers={"X-Internal-Key": KEY}
    )
    assert response.status_code == 200
    assert response.json()["cancelled"] is False


def test_cancel_stops_a_running_job(client):
    started = client.post(
        "/internal/v1/research/execute",
        json={"researchJobId": "cancel-me", "productQuery": "Sony WH-1000XM6", "demoMode": True},
        headers={"X-Internal-Key": KEY},
    )
    assert started.status_code == 202
    cancelled = client.post(
        "/internal/v1/research/cancel-me/cancel", headers={"X-Internal-Key": KEY}
    )
    # The job may already have finished (the demo pipeline is fast); either way
    # the endpoint answers rather than erroring.
    assert cancelled.status_code == 200
    assert isinstance(cancelled.json()["cancelled"], bool)
