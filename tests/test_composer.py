import pytest
from app.models.contexts import (
    CategoryContext,
    CustomerConsent,
    CustomerContext,
    CustomerIdentity,
    DigestItem,
    MerchantContext,
    MerchantIdentity,
    MerchantPerformance,
    TriggerContext,
)
from app.services.composer import engagement_composer


@pytest.mark.asyncio
async def test_composer_dentist_research():
    category = CategoryContext(
        slug="dentists",
        digest=[
            DigestItem(
                id="d_jida_01",
                title="JIDA Fluoride Study",
                summary="2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38%",
            )
        ],
    )
    merchant = MerchantContext(
        merchant_id="m_001",
        category_slug="dentists",
        identity=MerchantIdentity(
            name="Dr. Meera's Clinic",
            owner_first_name="Meera",
            city="Delhi",
            locality="Lajpat Nagar",
        ),
    )
    trigger = TriggerContext(
        id="trg_01",
        kind="research_digest",
        merchant_id="m_001",
        payload={"top_item_id": "d_jida_01"},
    )

    res = await engagement_composer.compose(category, merchant, trigger)
    body = res["body"]
    assert "Dr. Meera" in body
    assert "38%" in body
    assert "JIDA" in body or "Fluoride" in body
    assert len(res["rationale"]) > 0


@pytest.mark.asyncio
async def test_composer_customer_recall():
    category = CategoryContext(slug="dentists")
    merchant = MerchantContext(
        merchant_id="m_001",
        category_slug="dentists",
        identity=MerchantIdentity(name="Dr. Meera's Clinic", owner_first_name="Meera"),
    )
    customer = CustomerContext(
        customer_id="c_001",
        merchant_id="m_001",
        identity=CustomerIdentity(name="Priya", language_pref="en"),
        consent=CustomerConsent(scope=["recall_reminders"]),
    )
    trigger = TriggerContext(
        id="trg_02",
        scope="customer",
        kind="recall_due",
        merchant_id="m_001",
        customer_id="c_001",
        payload={
            "service_due": "6_month_cleaning",
            "available_slots": [{"label": "Wed 5 Nov, 6pm"}],
        },
    )

    res = await engagement_composer.compose(category, merchant, trigger, customer)
    body = res["body"]
    assert "Priya" in body
    assert "Wed 5 Nov, 6pm" in body
    assert "Dr. Meera" in body


@pytest.mark.asyncio
async def test_composer_festival_and_curious_ask():
    category = CategoryContext(slug="salons")
    merchant = MerchantContext(
        merchant_id="m_003",
        category_slug="salons",
        identity=MerchantIdentity(name="Studio11 Salon", owner_first_name="Lakshmi", locality="Kapra"),
    )

    # Festival trigger
    trg_fest = TriggerContext(
        id="trg_fest",
        kind="festival_upcoming",
        merchant_id="m_003",
        payload={"festival": "Diwali", "days_until": 188, "date": "2026-10-31"},
    )
    res_fest = await engagement_composer.compose(category, merchant, trg_fest)
    assert "Diwali" in res_fest["body"]
    assert "188" in res_fest["body"]

    # Curious ask trigger
    trg_ask = TriggerContext(
        id="trg_ask",
        kind="curious_ask_due",
        merchant_id="m_003",
        payload={},
    )
    res_ask = await engagement_composer.compose(category, merchant, trg_ask)
    assert "Lakshmi" in res_ask["body"]
    assert "Kapra" in res_ask["body"]
