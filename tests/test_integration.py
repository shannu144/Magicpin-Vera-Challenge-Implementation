import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.context_store import context_store
from app.services.conversation_store import conversation_store
from app.services.suppression import suppression_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean():
    context_store.clear()
    conversation_store.clear()
    suppression_engine.clear()


def test_full_lifecycle_integration():
    # 1. Healthz & Metadata
    res_h = client.get("/v1/healthz")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "ok"

    res_m = client.get("/v1/metadata")
    assert res_m.status_code == 200
    assert res_m.json()["team_name"] is not None

    # 2. Ingest Category
    client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "restaurants",
            "version": 1,
            "payload": {
                "slug": "restaurants",
                "category_name": "Restaurants",
                "voice": {"tone": "operator-oriented, energetic"},
            },
        },
    )

    # 3. Ingest Merchant
    client.post(
        "/v1/context",
        json={
            "scope": "merchant",
            "context_id": "m_pizza",
            "version": 1,
            "payload": {
                "merchant_id": "m_pizza",
                "category_slug": "restaurants",
                "identity": {"name": "SK Pizza Junction", "owner_first_name": "Suresh", "locality": "Sant Nagar"},
                "performance": {"views": 2200, "calls": 12},
                "offers": [{"id": "o_skpz_001", "title": "BOGO Pizza", "status": "active"}],
            },
        },
    )

    # 4. Ingest Trigger
    client.post(
        "/v1/context",
        json={
            "scope": "trigger",
            "context_id": "trg_ipl",
            "version": 1,
            "payload": {
                "id": "trg_ipl",
                "scope": "merchant",
                "kind": "ipl_match_today",
                "merchant_id": "m_pizza",
                "payload": {"match": "DC vs MI", "venue": "Arun Jaitley Stadium"},
                "urgency": 3,
                "suppression_key": "ipl:m_pizza:dc_mi",
                "expires_at": "2026-12-31T00:00:00Z",
            },
        },
    )

    # 5. POST /v1/tick
    res_tick = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T18:00:00Z", "available_triggers": ["trg_ipl"]},
    )
    assert res_tick.status_code == 200
    actions = res_tick.json()["actions"]
    assert len(actions) == 1
    act = actions[0]
    conv_id = act["conversation_id"]
    assert "DC vs MI" in act["body"]
    assert "Suresh" in act["body"]

    # 6. POST /v1/reply turn 2: "Tell me more"
    res_reply1 = client.post(
        "/v1/reply",
        json={
            "conversation_id": conv_id,
            "merchant_id": "m_pizza",
            "from_role": "merchant",
            "message": "Tell me more about how this works",
            "received_at": "2026-04-26T18:15:00Z",
            "turn_number": 2,
        },
    )
    assert res_reply1.status_code == 200
    assert res_reply1.json()["action"] == "send"

    # 7. POST /v1/reply turn 3: "Okay, let's do it" -> immediate action
    res_reply2 = client.post(
        "/v1/reply",
        json={
            "conversation_id": conv_id,
            "merchant_id": "m_pizza",
            "from_role": "merchant",
            "message": "Okay, let's do it.",
            "received_at": "2026-04-26T18:20:00Z",
            "turn_number": 3,
        },
    )
    assert res_reply2.status_code == 200
    assert res_reply2.json()["action"] == "send"
    assert "Action initiated" in res_reply2.json()["body"] or "complete" in res_reply2.json()["body"] or "Suresh" in res_reply2.json()["body"]
