import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.context_store import context_store
from app.services.conversation_store import conversation_store
from app.services.suppression import suppression_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_stores():
    context_store.clear()
    conversation_store.clear()
    suppression_engine.clear()


def test_tick_with_valid_trigger():
    # Ingest Category
    client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": {
                "slug": "dentists",
                "category_name": "Dentists",
                "voice": {"tone": "clinical, peer-oriented"},
                "digest": [
                    {
                        "id": "d_fluoride_01",
                        "title": "Fluoride Study",
                        "summary": "3-month fluoride recall cuts caries recurrence 38%",
                    }
                ],
            },
        },
    )

    # Ingest Merchant
    client.post(
        "/v1/context",
        json={
            "scope": "merchant",
            "context_id": "m_meera",
            "version": 1,
            "payload": {
                "merchant_id": "m_meera",
                "category_slug": "dentists",
                "identity": {"name": "Dr. Meera's Dental Clinic", "owner_first_name": "Meera", "locality": "Lajpat Nagar"},
                "performance": {"views": 2410, "calls": 18},
            },
        },
    )

    # Ingest Trigger
    client.post(
        "/v1/context",
        json={
            "scope": "trigger",
            "context_id": "trg_01",
            "version": 1,
            "payload": {
                "id": "trg_01",
                "scope": "merchant",
                "kind": "research_digest",
                "merchant_id": "m_meera",
                "payload": {"category": "dentists", "top_item_id": "d_fluoride_01"},
                "urgency": 2,
                "suppression_key": "res:dentists:2026",
                "expires_at": "2026-12-31T00:00:00Z",
            },
        },
    )

    # Call /v1/tick
    res = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:30:00Z", "available_triggers": ["trg_01"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["actions"]) == 1
    act = data["actions"][0]
    assert act["merchant_id"] == "m_meera"
    assert act["trigger_id"] == "trg_01"
    assert "Dr. Meera" in act["body"]
    assert "38%" in act["body"]
    assert len(act["rationale"]) > 0


def test_tick_missing_context_safety():
    # Only trigger exists, merchant does not -> must skip safely without crashing
    client.post(
        "/v1/context",
        json={
            "scope": "trigger",
            "context_id": "trg_missing",
            "version": 1,
            "payload": {
                "id": "trg_missing",
                "merchant_id": "m_nonexistent",
                "kind": "perf_dip",
            },
        },
    )

    res = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:30:00Z", "available_triggers": ["trg_missing", "trg_completely_unknown"]},
    )
    assert res.status_code == 200
    assert res.json()["actions"] == []


def test_tick_expired_trigger():
    client.post(
        "/v1/context",
        json={
            "scope": "trigger",
            "context_id": "trg_exp",
            "version": 1,
            "payload": {
                "id": "trg_exp",
                "merchant_id": "m_meera",
                "kind": "perf_dip",
                "expires_at": "2026-01-01T00:00:00Z",
            },
        },
    )
    res = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:30:00Z", "available_triggers": ["trg_exp"]},
    )
    assert res.status_code == 200
    assert res.json()["actions"] == []
