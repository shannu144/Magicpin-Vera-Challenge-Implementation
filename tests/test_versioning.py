import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.context_store import context_store
from app.services.suppression import suppression_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_data():
    context_store.clear()
    suppression_engine.clear()


def test_dynamic_version_update_in_tick():
    # Ingest Category
    client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": {"slug": "dentists"},
        },
    )

    # Ingest Merchant v1 with 2410 views
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
                "performance": {"views": 2410, "calls": 18, "delta_7d": {"calls_pct": -0.05}},
            },
        },
    )

    # Ingest Trigger
    client.post(
        "/v1/context",
        json={
            "scope": "trigger",
            "context_id": "trg_dip",
            "version": 1,
            "payload": {
                "id": "trg_dip",
                "scope": "merchant",
                "kind": "perf_dip",
                "merchant_id": "m_meera",
                "payload": {"metric": "calls", "delta_pct": -0.05},
                "suppression_key": "dip:m_meera:v1",
            },
        },
    )

    # First Tick
    res1 = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_dip"]},
    ).json()
    assert len(res1["actions"]) == 1
    assert "2410" in res1["actions"][0]["body"]

    # Now Judge pushes Merchant v2 with updated performance: 4890 views
    client.post(
        "/v1/context",
        json={
            "scope": "merchant",
            "context_id": "m_meera",
            "version": 2,
            "payload": {
                "merchant_id": "m_meera",
                "category_slug": "dentists",
                "identity": {"name": "Dr. Meera's Dental Clinic", "owner_first_name": "Meera"},
                "performance": {"views": 4890, "calls": 25, "delta_7d": {"calls_pct": -0.15}},
            },
        },
    )

    # Push a new trigger v2
    client.post(
        "/v1/context",
        json={
            "scope": "trigger",
            "context_id": "trg_dip_v2",
            "version": 1,
            "payload": {
                "id": "trg_dip_v2",
                "scope": "merchant",
                "kind": "perf_dip",
                "merchant_id": "m_meera",
                "payload": {"metric": "calls", "delta_pct": -0.15},
                "suppression_key": "dip:m_meera:v2",
            },
        },
    )

    # Second Tick with updated context
    res2 = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:30:00Z", "available_triggers": ["trg_dip_v2"]},
    ).json()
    assert len(res2["actions"]) == 1
    # Must reflect version 2 data (4890), not stale version 1 data (2410)
    assert "4890" in res2["actions"][0]["body"]
    assert "2410" not in res2["actions"][0]["body"]
