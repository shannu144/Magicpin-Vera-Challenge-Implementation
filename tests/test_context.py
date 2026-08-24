import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.context_store import context_store

client = TestClient(app)


def setup_function():
    context_store.clear()


def test_new_context_ingestion():
    res = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": {"slug": "dentists", "category_name": "Dentists"},
            "delivered_at": "2026-04-26T10:00:00Z",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert data["ack_id"] == "ack_category_dentists_v1"
    assert "stored_at" in data


def test_duplicate_version_idempotent():
    payload = {"slug": "dentists", "category_name": "Dentists"}
    res1 = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": payload,
        },
    )
    assert res1.json()["accepted"] is True
    stored_at_1 = res1.json()["stored_at"]

    res2 = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": payload,
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["accepted"] is True
    assert data2["stored_at"] == stored_at_1


def test_version_upgrade_and_stale_rejection():
    # v1
    client.post(
        "/v1/context",
        json={"scope": "merchant", "context_id": "m_001", "version": 1, "payload": {"val": 1}},
    )

    # v3
    res_v3 = client.post(
        "/v1/context",
        json={"scope": "merchant", "context_id": "m_001", "version": 3, "payload": {"val": 3}},
    )
    assert res_v3.json()["accepted"] is True

    # v2 (stale because v3 is current)
    res_stale = client.post(
        "/v1/context",
        json={"scope": "merchant", "context_id": "m_001", "version": 2, "payload": {"val": 2}},
    )
    assert res_stale.status_code == 200
    data = res_stale.json()
    assert data["accepted"] is False
    assert data["reason"] == "stale_version"
    assert data["current_version"] == 3


def test_invalid_scope():
    res = client.post(
        "/v1/context",
        json={"scope": "invalid_scope", "context_id": "test_001", "version": 1, "payload": {}},
    )
    assert res.status_code == 422 or res.status_code == 400
