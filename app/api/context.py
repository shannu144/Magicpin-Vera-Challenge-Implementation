from fastapi import APIRouter, HTTPException
from app.models.requests import ContextPushRequest
from app.models.responses import (
    ContextPushAcceptedResponse,
    ContextPushResponse,
    ContextPushStaleResponse,
)
from app.services.context_store import context_store

router = APIRouter()


@router.post("/v1/context", response_model=ContextPushResponse)
def post_context(req: ContextPushRequest):
    if req.scope not in ("category", "merchant", "customer", "trigger"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope '{req.scope}'. Must be one of category, merchant, customer, trigger.",
        )

    accepted, stored_at_or_reason, current_version = context_store.put(
        scope=req.scope,
        context_id=req.context_id,
        version=req.version,
        payload=req.payload,
        delivered_at=req.delivered_at,
    )

    if not accepted:
        return ContextPushStaleResponse(
            accepted=False,
            reason=stored_at_or_reason or "stale_version",
            current_version=current_version or 0,
        )

    return ContextPushAcceptedResponse(
        accepted=True,
        ack_id=f"ack_{req.scope}_{req.context_id}_v{req.version}",
        stored_at=stored_at_or_reason or "",
    )
