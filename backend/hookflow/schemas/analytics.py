"""Analytics schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class AnalyticsResponse(BaseModel):
    """Analytics overview response."""

    total_webhooks: int
    success_rate: float
    avg_response_time_ms: float
    webhooks_by_status: dict[str, int]
    webhooks_over_time: list[dict[str, int | str]]
    top_destinations: list[dict[str, int | float | str]]


class TimeSeriesDataPoint(BaseModel):
    """Time series data point."""

    timestamp: str
    count: int


class DestinationStats(BaseModel):
    """Destination statistics."""

    name: str
    count: int
    success_rate: float
