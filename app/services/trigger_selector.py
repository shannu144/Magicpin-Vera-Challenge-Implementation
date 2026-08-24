from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from app.models.contexts import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)
from app.services.context_store import context_store
from app.services.suppression import suppression_engine


class TriggerCandidate:
    def __init__(
        self,
        trigger: TriggerContext,
        merchant: MerchantContext,
        category: CategoryContext,
        customer: Optional[CustomerContext] = None,
        rank_score: float = 0.0,
    ):
        self.trigger = trigger
        self.merchant = merchant
        self.category = category
        self.customer = customer
        self.rank_score = rank_score


class TriggerSelector:
    """
    Evaluates, filters, ranks, and selects the most impactful triggers for /v1/tick.
    """

    def is_expired(self, expires_at: Optional[str], now_str: str) -> bool:
        if not expires_at:
            return False
        try:
            # Simple ISO comparison or parsing
            exp = expires_at.replace("Z", "+00:00")
            now = now_str.replace("Z", "+00:00")
            return exp < now
        except Exception:
            return False

    def select_triggers(
        self,
        available_trigger_ids: List[str],
        now_str: str,
        max_actions: int = 20,
    ) -> List[TriggerCandidate]:
        candidates: List[TriggerCandidate] = []

        for trg_id in available_trigger_ids:
            # 1. Retrieve TriggerContext
            trigger = context_store.get_trigger(trg_id)
            if not trigger:
                # Missing trigger context - safe skip
                continue

            # 2. Check expiry
            if self.is_expired(trigger.expires_at, now_str):
                continue

            # 3. Retrieve MerchantContext
            merchant = context_store.get_merchant(trigger.merchant_id)
            if not merchant:
                # Missing merchant context - safe skip
                continue

            # 4. Retrieve CategoryContext
            category = context_store.get_category(merchant.category_slug)
            if not category:
                # Missing category context - safe skip
                continue

            # 5. Customer Context if applicable
            customer: Optional[CustomerContext] = None
            if trigger.customer_id:
                customer = context_store.get_customer(trigger.customer_id)
                if not customer and trigger.scope == "customer":
                    # Required customer missing
                    continue

                # Check customer consent
                if customer and customer.consent:
                    consent_scopes = customer.consent.scope or []
                    kind = trigger.kind.lower()
                    if "recall" in kind and "recall_reminders" not in consent_scopes and "appointment_reminders" not in consent_scopes:
                        continue
                    if "promotional" in kind and "promotional_offers" not in consent_scopes:
                        continue
                    if not consent_scopes:
                        continue

            # 6. Check suppression
            suppressed, _ = suppression_engine.is_suppressed(
                suppression_key=trigger.suppression_key,
                merchant_id=merchant.merchant_id,
            )
            if suppressed:
                continue

            # 7. Calculate Rank Score
            # Urgency (1 to 5) * 10 + relevance factors
            urgency = getattr(trigger, "urgency", 1)
            rank = urgency * 10.0

            # Bonus for high-engagement merchants or active planning
            if "active_planning" in trigger.kind or urgency >= 4:
                rank += 20.0
            if "research_digest" in trigger.kind:
                rank += 15.0
            if trigger.scope == "customer":
                rank += 12.0

            candidates.append(
                TriggerCandidate(
                    trigger=trigger,
                    merchant=merchant,
                    category=category,
                    customer=customer,
                    rank_score=rank,
                )
            )

        # Sort descending by rank_score
        candidates.sort(key=lambda c: c.rank_score, reverse=True)
        return candidates[:max_actions]


trigger_selector = TriggerSelector()
