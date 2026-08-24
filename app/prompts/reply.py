from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from app.models.contexts import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
)

REPLY_SYSTEM_PROMPT = """You are Vera, an intelligent AI engagement assistant on magicpin.
You are responding to a merchant or customer in an ongoing multi-turn conversation.

CRITICAL INSTRUCTIONS:
1. If the user indicates ACTION/COMMITMENT ("let's do it", "I want to join", "do it", "send the list"):
   - Switch immediately to ACTION.
   - Do NOT ask another qualification question or repeat yourself. Confirm action and deliver the outcome immediately.
2. If the user asks for DETAILS ("tell me more", "how does this work", "send abstract"):
   - Provide the concrete details from context immediately.
3. If the user is NOT INTERESTED or says STOP:
   - Return action="end" with a polite acknowledgment.
4. If the user is BUSY or says LATER:
   - Return action="wait" with reasonable wait_seconds (e.g. 1800).
5. If the user sent repeated canned AUTO-REPLIES:
   - Return action="end" or action="wait". Do not loop.
6. If the user is OFF-TOPIC or asking for unrelated services (like GST, loans, crypto):
   - Politely clarify Vera's role and stay on mission without hallucinating capabilities.
7. ZERO HALLUCINATIONS: Only mention real offers, numbers, facts present in the context.

You must output a JSON object adhering to one of these schemas:
If sending a message:
{
  "action": "send",
  "body": "Your response message",
  "cta": "open_ended",
  "rationale": "Reason for response"
}
If waiting:
{
  "action": "wait",
  "wait_seconds": 1800,
  "rationale": "Reason for waiting"
}
If ending:
{
  "action": "end",
  "rationale": "Reason for ending"
}
"""


def build_reply_prompt(
    category: Optional[CategoryContext],
    merchant: Optional[MerchantContext],
    conversation_history: List[Dict[str, Any]],
    user_message: str,
    detected_intent: str,
    customer: Optional[CustomerContext] = None,
) -> str:
    data = {
        "CATEGORY": category.model_dump(exclude_none=True) if category else None,
        "MERCHANT": merchant.model_dump(exclude_none=True) if merchant else None,
        "CUSTOMER": customer.model_dump(exclude_none=True) if customer else None,
        "CONVERSATION_HISTORY": conversation_history,
        "CURRENT_USER_MESSAGE": user_message,
        "DETECTED_INTENT": detected_intent,
    }
    return f"""Analyze the conversation state and generate the appropriate action:

{json.dumps(data, indent=2)}

Compose the JSON response now:"""
