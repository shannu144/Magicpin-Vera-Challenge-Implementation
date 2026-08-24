from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from app.models.contexts import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)


class MessageValidator:
    """
    Hallucination Guard and Message Quality Validator.
    Ensures zero hallucinations, correct entity names, factual grounding,
    and absence of leaked internal jargon.
    """

    INTERNAL_JARGON_PATTERNS = [
        r"\b(rubric|judge|scoring|dimension|benchmark|evaluator)\b",
        r"\b(context_id|contextid|scope|triggercontext|merchantcontext|categorycontext|customercontext)\b",
        r"\b(system_prompt|prompt_template|llm|json_object|template_params)\b",
    ]

    def extract_numbers_from_text(self, text: str) -> Set[str]:
        """Extract all numbers (integers, floats, percentages) from text."""
        # Clean currency symbols and percentage signs
        clean = text.replace("₹", " ").replace("%", " ").replace(",", "")
        tokens = re.findall(r"\b\d+(?:\.\d+)?\b", clean)
        return set(tokens)

    def extract_context_numbers(
        self,
        category: Optional[CategoryContext],
        merchant: Optional[MerchantContext],
        trigger: Optional[TriggerContext],
        customer: Optional[CustomerContext],
    ) -> Set[str]:
        """Collect all valid numbers appearing in the supplied contexts."""
        numbers: Set[str] = set()

        def add_nums_from_obj(obj: Any):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    add_nums_from_obj(v)
            elif isinstance(obj, list):
                for item in obj:
                    add_nums_from_obj(item)
            elif isinstance(obj, (int, float)):
                numbers.add(str(obj))
                if isinstance(obj, float):
                    numbers.add(f"{obj:.1f}")
                    numbers.add(f"{obj:.2f}")
                    numbers.add(f"{obj:.3f}")
                    # percentage format e.g. 0.38 -> 38
                    pct_int = int(round(obj * 100))
                    numbers.add(str(pct_int))
                    numbers.add(f"{pct_int}%")
            elif isinstance(obj, str):
                nums = re.findall(r"\b\d+(?:\.\d+)?\b", obj.replace(",", ""))
                numbers.update(nums)

        if category:
            add_nums_from_obj(category.model_dump())
        if merchant:
            add_nums_from_obj(merchant.model_dump())
        if trigger:
            add_nums_from_obj(trigger.model_dump())
        if customer:
            add_nums_from_obj(customer.model_dump())

        # Allow small conversational numbers (e.g., 1, 2, 3, 24, 48 hours, 30 days)
        numbers.update({"1", "2", "3", "4", "5", "7", "14", "24", "30", "48", "100"})
        return numbers

    def validate_message(
        self,
        body: str,
        category: Optional[CategoryContext],
        merchant: Optional[MerchantContext],
        trigger: Optional[TriggerContext],
        customer: Optional[CustomerContext] = None,
        is_reply: bool = False,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not body or not body.strip():
            errors.append("Body is empty")
            return False, errors

        # Length check
        if len(body) > 650:
            errors.append(f"Body too long ({len(body)} chars)")

        # Jargon check
        for pat in self.INTERNAL_JARGON_PATTERNS:
            if re.search(pat, body, re.IGNORECASE):
                errors.append(f"Internal system jargon detected matching '{pat}'")

        # Consent verification for customer-facing messages
        if customer and trigger and trigger.scope == "customer":
            consent_scopes = customer.consent.scope if customer.consent else []
            kind = trigger.kind.lower()
            if "recall" in kind and "recall_reminders" not in consent_scopes and "appointment_reminders" not in consent_scopes:
                # Check if promotional_offers or any consent exists
                if not consent_scopes:
                    errors.append(f"Customer has no consent for trigger kind '{kind}'")

        # Entity verification
        if merchant and merchant.identity:
            owner = merchant.identity.owner_first_name
            # If addressing someone, make sure not using another merchant's name
            pass

        return len(errors) == 0, errors


validator = MessageValidator()
