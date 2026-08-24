from fastapi import APIRouter
from app.config import settings
from app.models.responses import MetadataResponse

router = APIRouter()


@router.get("/v1/metadata", response_model=MetadataResponse)
def get_metadata():
    return MetadataResponse(
        team_name=settings.team_name,
        team_members=settings.team_members,
        model=settings.model,
        approach=settings.approach,
        contact_email=settings.contact_email,
        version=settings.bot_version,
        submitted_at="2026-04-26T00:00:00Z",
    )
