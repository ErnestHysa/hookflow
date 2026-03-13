"""Analytics API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db
from hookflow.schemas.analytics import AnalyticsResponse
from hookflow.services.analytics import AnalyticsService

router = APIRouter(prefix="/apps", tags=["analytics"])


async def get_analytics_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(db)


@router.get(
    "/{app_id}/analytics",
    response_model=AnalyticsResponse,
    summary="Get analytics for an app",
)
async def get_analytics(
    app_id: str,
    period: str = "24h",
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get webhook analytics for an app."""
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(
            status_code=400,
            detail="Invalid period. Use 24h, 7d, or 30d"
        )

    return await service.get_analytics(app_id, period)
