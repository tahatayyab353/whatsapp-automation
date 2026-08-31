from fastapi import APIRouter
from app.core.config import settings
from app.schemas.common import SystemInfoResponse

router = APIRouter()


@router.get(
    "/system/info",
    response_model=SystemInfoResponse,
    summary="System Information",
    description="Returns public non-sensitive system metadata including service name, version, and runtime environment.",
)
async def get_system_info() -> SystemInfoResponse:
    return SystemInfoResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

