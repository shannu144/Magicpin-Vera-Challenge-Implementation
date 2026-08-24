from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ContextPushAcceptedResponse(BaseModel):
    accepted: Literal[True] = True
    ack_id: str
    stored_at: str


class ContextPushStaleResponse(BaseModel):
    accepted: Literal[False] = False
    reason: str = "stale_version"
    current_version: int


ContextPushResponse = Union[ContextPushAcceptedResponse, ContextPushStaleResponse]


class HealthContextCounts(BaseModel):
    category: int = 0
    merchant: int = 0
    customer: int = 0
    trigger: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: int
    contexts_loaded: HealthContextCounts


class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str = "vera"
    trigger_id: str
    template_name: str
    template_params: List[str] = Field(default_factory=list)
    body: str
    cta: str = "open_ended"
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: List[TickAction] = Field(default_factory=list)


class ReplySendAction(BaseModel):
    action: Literal["send"] = "send"
    body: str
    cta: str = "open_ended"
    rationale: str


class ReplyWaitAction(BaseModel):
    action: Literal["wait"] = "wait"
    wait_seconds: int = 1800
    rationale: str


class ReplyEndAction(BaseModel):
    action: Literal["end"] = "end"
    rationale: str


ReplyResponse = Union[ReplySendAction, ReplyWaitAction, ReplyEndAction]
