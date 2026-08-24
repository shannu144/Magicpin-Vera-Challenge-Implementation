from fastapi import APIRouter
from app.models.requests import TickRequest
from app.models.responses import TickAction, TickResponse
from app.services.composer import engagement_composer
from app.services.conversation_store import conversation_store
from app.services.suppression import suppression_engine
from app.services.trigger_selector import trigger_selector

router = APIRouter()


@router.post("/v1/tick", response_model=TickResponse)
async def post_tick(req: TickRequest):
    candidates = trigger_selector.select_triggers(
        available_trigger_ids=req.available_triggers,
        now_str=req.now,
        max_actions=20,
    )

    actions = []
    for c in candidates:
        comp = await engagement_composer.compose(
            category=c.category,
            merchant=c.merchant,
            trigger=c.trigger,
            customer=c.customer,
        )

        conv_id = f"conv_{c.trigger.id}_{c.merchant.merchant_id}"
        if c.customer:
            conv_id += f"_{c.customer.customer_id}"

        suppression_k = comp.get(
            "suppression_key",
            c.trigger.suppression_key or f"{c.trigger.kind}:{c.merchant.merchant_id}",
        )

        action = TickAction(
            conversation_id=conv_id,
            merchant_id=c.merchant.merchant_id,
            customer_id=c.customer.customer_id if c.customer else None,
            send_as=comp.get("send_as", "vera"),
            trigger_id=c.trigger.id,
            template_name=comp.get("template_name", f"vera_{c.category.slug}_v1"),
            template_params=comp.get("template_params", []),
            body=comp["body"],
            cta=comp.get("cta", "open_ended"),
            suppression_key=suppression_k,
            rationale=comp.get("rationale", "Proactive trigger engagement"),
        )
        actions.append(action)

        # Record suppression
        suppression_engine.record_sent(
            suppression_key=action.suppression_key,
            merchant_id=action.merchant_id,
            body=action.body,
            conversation_id=action.conversation_id,
            timestamp=req.now,
        )

        # Record conversation initial turn
        conversation_store.record_proactive_tick(
            conversation_id=action.conversation_id,
            merchant_id=action.merchant_id,
            customer_id=action.customer_id,
            trigger_id=action.trigger_id,
            body=action.body,
            action_dict=action.model_dump(),
            timestamp=req.now,
        )

    return TickResponse(actions=actions)
