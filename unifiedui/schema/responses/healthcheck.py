from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
