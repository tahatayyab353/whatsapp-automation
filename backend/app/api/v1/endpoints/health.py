from fastapi import APIRouter
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API v1 Health Check",
    description="Returns the operational health status of the v1 API for monitoring and container health checks.",
)
async def get_v1_health() -> HealthResponse:
    return HealthResponse(status="ok")

