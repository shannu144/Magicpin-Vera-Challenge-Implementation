import pytest
from app.services.suppression import SuppressionEngine


def test_suppression_engine():
    engine = SuppressionEngine()

    # 1. New suppression key
    suppressed, reason = engine.is_suppressed("key_001", "m_001")
    assert not suppressed

    # Record sent
    engine.record_sent(
        suppression_key="key_001",
        merchant_id="m_001",
        body="Hello world",
        conversation_id="conv_01",
    )

    # 2. Check duplicate suppression key
    suppressed, reason = engine.is_suppressed("key_001", "m_001")
    assert suppressed

    # 3. Check duplicate body per merchant
    suppressed, reason = engine.is_suppressed(
        suppression_key=None,
        merchant_id="m_001",
        body="Hello world",
    )
    assert suppressed

    # 4. Different merchant with same body is allowed
    suppressed, reason = engine.is_suppressed(
        suppression_key=None,
        merchant_id="m_002",
        body="Hello world",
    )
    assert not suppressed
