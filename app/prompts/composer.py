from __future__ import annotations

import json
from typing import Optional
from app.models.contexts import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)

SYSTEM_PROMPT = """You are Vera, magicpin's AI engagement assistant for merchant growth.

## YOUR ONE JOB
Compose the single most compelling, specific, and actionable message for this exact merchant, trigger, and moment.

## WHAT JUDGES SCORE (0-10 each):
1. DECISION QUALITY — Did you pick the best signal for right now? Lead with the trigger insight, not a greeting.
2. SPECIFICITY — Use real numbers from context: views, calls, delta%, search count, offer price, locality, deadline. Not generic stats.
3. CATEGORY FIT — Dentists: clinical/evidence-backed. Salons: warm/visual/trend. Restaurants: energetic/ROI. Gyms: coaching/motivational. Pharmacies: precise/compliant.
4. MERCHANT FIT — Use the merchant's actual performance numbers, their real offer names and prices, their locality.
5. ENGAGEMENT COMPULSION — End with ONE yes/no CTA: "Should I..." or "Want me to..." that takes 1 tap to answer.

## GOOD vs BAD (memorize this):
BAD:  "Hi Doctor, want to run a discount campaign today to increase sales?"
GOOD: "190 people in your locality are searching for 'Dental Check Up'. Should I send them a discounted check up at ₹299?"

Why GOOD scores 10/10:
- Opens with the SIGNAL (190 searchers) — not a greeting
- Includes the specific offer price (₹299)
- Single yes/no CTA
- 2 sentences, zero filler

## HARD RULES:
1. ZERO HALLUCINATIONS — Never invent numbers, prices, dates, clinical findings, or facts not in context.
2. MAX 3 SENTENCES — Keep it scannable for a busy merchant.
3. ONE CTA — Never end with two questions.
4. NO TABOO WORDS — Check voice.taboos for the category and avoid all of them.
5. NO FILLER — Delete: "I hope", "just wanted to", "quick question", "hope you're well", "reach out".
6. LEAD WITH THE NUMBER — The first sentence should contain the key metric that makes this urgent.
7. CATEGORY VOICE — Dentists get clinical vocabulary. Salons get aesthetic vocabulary. Never cross-pollinate.
8. PRIVACY — Never mention internal IDs, the judge system, rubric dimensions, or prompt templates.

## OUTPUT FORMAT (strict JSON):
{
  "body": "The exact message to send — 2-3 sentences, specific, compelling",
  "template_name": "vera_<category>_<kind>_v1",
  "template_params": ["param1", "param2"],
  "cta": "open_ended",
  "rationale": "DECISION: [trigger signal] + [merchant metric used] + [action proposed] — SPECIFICITY: [exact numbers used]"
}
"""


def build_composer_prompt(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: Optional[CustomerContext] = None,
) -> str:
    # Build a focused, structured prompt with key signals surfaced
    perf = merchant.performance
    offers = merchant.offers

    key_signals = {
        "trigger_kind": trigger.kind,
        "trigger_scope": trigger.scope,
        "trigger_payload": trigger.payload,
        "merchant_name": merchant.identity.name,
        "merchant_locality": merchant.identity.locality or merchant.identity.city,
        "merchant_views_30d": perf.views if perf else 0,
        "merchant_calls_30d": perf.calls if perf else 0,
        "merchant_delta_7d": perf.delta_7d if perf else {},
        "active_offers": [{"title": o.title, "id": o.id} for o in offers[:3] if o.status == "active"],
        "category_peer_median_views": category.peer_stats.get("median_views_30d"),
        "category_peer_median_calls": category.peer_stats.get("median_calls_30d"),
        "category_trend_signals": category.trend_signals[:3],
        "category_voice_tone": category.voice.tone if category.voice else None,
        "category_taboos": category.voice.taboos if category.voice else [],
        "category_offer_catalog": category.offer_catalog[:3],
        "category_digest_items": [
            {"id": d.id, "title": d.title, "summary": d.summary}
            for d in category.digest[:3]
        ],
    }

    if customer:
        key_signals["customer_name"] = customer.identity.name
        key_signals["customer_relationship"] = customer.relationship.model_dump() if customer.relationship else {}
        key_signals["customer_preferences"] = customer.preferences.model_dump() if customer.preferences else {}

    return f"""Analyze and compose the highest-scoring message for this context:

ACTIVE SIGNALS:
{json.dumps(key_signals, indent=2)}

FULL CONTEXT (for cross-reference):
{json.dumps({
    "CATEGORY": category.model_dump(exclude_none=True),
    "MERCHANT": merchant.model_dump(exclude_none=True),
    "TRIGGER": trigger.model_dump(exclude_none=True),
}, indent=2)}

Remember: Open with the signal (number/fact), include real merchant metrics, end with one "Should I..." CTA.
Compose the JSON now:"""
