from datetime import datetime, UTC
from fastapi import APIRouter, status

from unifiedui.schema.responses.healthcheck import HealthCheckResponse


router = APIRouter()


@router.get(
    "/healthcheck",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns the health status of the API"
)
async def healthcheck() -> HealthCheckResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthCheckResponse: Current health status of the service
    """
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
        version="1.0.0"
    )
