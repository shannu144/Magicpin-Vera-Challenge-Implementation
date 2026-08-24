from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    turn_number: int
    from_role: str  # "merchant" | "customer" | "vera"
    message: str
    received_at: str
    action_taken: Optional[Dict[str, Any]] = None


class ConversationState(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    trigger_id: Optional[str] = None
    status: str = "active"  # active | waiting | ended
    current_intent: Optional[str] = None
    turns: List[ConversationTurn] = Field(default_factory=list)
    last_action: Optional[str] = None
    last_user_message: Optional[str] = None
    consecutive_auto_replies: int = 0
    created_at: str
    updated_at: str


class ConversationStore:
    """
    Thread-safe in-memory store for multi-turn conversation states.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._conversations: Dict[str, ConversationState] = {}

    def get_or_create(
        self,
        conversation_id: str,
        merchant_id: str,
        customer_id: Optional[str] = None,
        trigger_id: Optional[str] = None,
    ) -> ConversationState:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            if conversation_id not in self._conversations:
                state = ConversationState(
                    conversation_id=conversation_id,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                    trigger_id=trigger_id,
                    status="active",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                self._conversations[conversation_id] = state
            return self._conversations[conversation_id]

    def get(self, conversation_id: str) -> Optional[ConversationState]:
        with self._lock:
            return self._conversations.get(conversation_id)

    def record_proactive_tick(
        self,
        conversation_id: str,
        merchant_id: str,
        customer_id: Optional[str],
        trigger_id: str,
        body: str,
        action_dict: Dict[str, Any],
        timestamp: str,
    ):
        with self._lock:
            state = self.get_or_create(
                conversation_id=conversation_id,
                merchant_id=merchant_id,
                customer_id=customer_id,
                trigger_id=trigger_id,
            )
            state.turns.append(
                ConversationTurn(
                    turn_number=1,
                    from_role="vera",
                    message=body,
                    received_at=timestamp,
                    action_taken=action_dict,
                )
            )
            state.last_action = "send"
            state.updated_at = timestamp

    def add_user_turn(
        self,
        conversation_id: str,
        merchant_id: str,
        customer_id: Optional[str],
        from_role: str,
        message: str,
        received_at: str,
        turn_number: int,
        intent: str,
    ) -> ConversationState:
        with self._lock:
            state = self.get_or_create(
                conversation_id=conversation_id,
                merchant_id=merchant_id,
                customer_id=customer_id,
            )
            # Check for repeated canned auto-reply message
            cleaned_prev = (
                state.last_user_message.strip().lower()
                if state.last_user_message
                else ""
            )
            cleaned_curr = message.strip().lower()

            if intent == "auto_reply" or (
                cleaned_prev and cleaned_prev == cleaned_curr
            ):
                state.consecutive_auto_replies += 1
            else:
                state.consecutive_auto_replies = 0

            state.last_user_message = message
            state.current_intent = intent
            state.updated_at = received_at

            state.turns.append(
                ConversationTurn(
                    turn_number=turn_number,
                    from_role=from_role,
                    message=message,
                    received_at=received_at,
                )
            )
            return state

    def record_bot_reply(
        self,
        conversation_id: str,
        action: str,  # send | wait | end
        body: Optional[str],
        action_dict: Dict[str, Any],
        timestamp: str,
    ):
        with self._lock:
            state = self.get(conversation_id)
            if not state:
                return
            state.last_action = action
            state.updated_at = timestamp
            if action == "end":
                state.status = "ended"
            elif action == "wait":
                state.status = "waiting"
            else:
                state.status = "active"

            if body:
                turn_no = (
                    len(state.turns) + 1
                    if state.turns
                    else 2
                )
                state.turns.append(
                    ConversationTurn(
                        turn_number=turn_no,
                        from_role="vera",
                        message=body,
                        received_at=timestamp,
                        action_taken=action_dict,
                    )
                )

    def clear(self):
        with self._lock:
            self._conversations.clear()


conversation_store = ConversationStore()
