from fastapi import APIRouter
from app.models.responses import HealthContextCounts, HealthResponse
from app.services.context_store import context_store
from app.utils.timing import get_uptime_seconds

router = APIRouter()


@router.get("/v1/healthz", response_model=HealthResponse)
def get_healthz():
    counts = context_store.get_counts_by_scope()
    return HealthResponse(
        status="ok",
        uptime_seconds=get_uptime_seconds(),
        contexts_loaded=HealthContextCounts(**counts),
    )
