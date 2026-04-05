from datetime import datetime, timezone

from fastapi import APIRouter

from api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
    )
