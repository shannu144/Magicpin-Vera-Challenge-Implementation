import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.context_store import context_store
from app.services.conversation_store import conversation_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_data():
    context_store.clear()
    conversation_store.clear()

    # Load merchant
    client.post(
        "/v1/context",
        json={
            "scope": "merchant",
            "context_id": "m_meera",
            "version": 1,
            "payload": {
                "merchant_id": "m_meera",
                "category_slug": "dentists",
                "identity": {"name": "Dr. Meera's Dental Clinic", "owner_first_name": "Meera"},
                "subscription": {"status": "active", "plan": "Pro"},
            },
        },
    )


def test_reply_immediate_action_transition():
    # User says "Okay, let's do it." -> must return action="send" and immediately confirm action without asking redundant qualification
    res = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_test_action",
            "merchant_id": "m_meera",
            "from_role": "merchant",
            "message": "Okay, let's do it.",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "send"
    assert "body" in data
    assert "Dr. Meera" in data["body"] or "Action initiated" in data["body"] or "complete" in data["body"]


def test_reply_not_interested():
    res = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_test_no",
            "merchant_id": "m_meera",
            "from_role": "merchant",
            "message": "No, not interested. Stop messaging.",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "end"


def test_reply_busy_later():
    res = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_test_busy",
            "merchant_id": "m_meera",
            "from_role": "merchant",
            "message": "Busy right now, message me later",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "wait"
    assert data["wait_seconds"] > 0


def test_reply_autoreply_loop_breaker():
    conv_id = "conv_test_ar"
    auto_text = "Thank you for contacting us. We will get back to you shortly."

    res1 = client.post(
        "/v1/reply",
        json={
            "conversation_id": conv_id,
            "merchant_id": "m_meera",
            "from_role": "merchant",
            "message": auto_text,
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 1,
        },
    ).json()

    res2 = client.post(
        "/v1/reply",
        json={
            "conversation_id": conv_id,
            "merchant_id": "m_meera",
            "from_role": "merchant",
            "message": auto_text,
            "received_at": "2026-04-26T10:46:00Z",
            "turn_number": 2,
        },
    ).json()

    # Second consecutive auto-reply must break loop
    assert res2["action"] in ("end", "wait")
