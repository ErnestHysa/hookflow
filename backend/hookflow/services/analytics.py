"""Analytics service for webhook statistics."""

from datetime import datetime, timedelta
from sqlalchemy import case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Float

from hookflow.models.app import Delivery, Destination, Webhook
from hookflow.schemas.analytics import AnalyticsResponse


class AnalyticsService:
    """Service for computing webhook analytics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_analytics(
        self,
        app_id: str,
        period: str = "24h",
    ) -> AnalyticsResponse:
        """
        Get analytics for an app over a time period.

        Args:
            app_id: Application ID
            period: Time period (24h, 7d, 30d)

        Returns:
            AnalyticsResponse with aggregated statistics
        """
        # Calculate time range
        now = datetime.utcnow()
        if period == "24h":
            start_time = now - timedelta(hours=24)
            bucket = "hour"
        elif period == "7d":
            start_time = now - timedelta(days=7)
            bucket = "day"
        else:  # 30d
            start_time = now - timedelta(days=30)
            bucket = "day"

        # Total webhooks
        total_result = await self.db.execute(
            select(func.count())
            .select_from(Webhook)
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
        )
        total_webhooks = total_result.scalar() or 0

        # Success rate (completed vs total)
        completed_result = await self.db.execute(
            select(func.count())
            .select_from(Webhook)
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .where(Webhook.status == "completed")
        )
        completed = completed_result.scalar() or 0
        success_rate = (completed / total_webhooks * 100) if total_webhooks > 0 else 0

        # Avg response time
        avg_time_result = await self.db.execute(
            select(func.avg(Delivery.response_time_ms))
            .join(Webhook, Webhook.id == Delivery.webhook_id)
            .where(Webhook.app_id == app_id)
            .where(Delivery.response_time_ms.isnot(None))
            .where(Webhook.created_at >= start_time)
        )
        avg_response_time = avg_time_result.scalar() or 0

        # Webhooks by status
        status_result = await self.db.execute(
            select(Webhook.status, func.count())
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .group_by(Webhook.status)
        )
        webhooks_by_status = {status: count for status, count in status_result.all()}

        # Webhooks over time - use date_trunc for PostgreSQL
        # Fall back to simpler grouping for SQLite
        try:
            time_series_result = await self.db.execute(
                select(
                    func.date_trunc(bucket, Webhook.created_at).label("time"),
                    func.count(),
                )
                .where(Webhook.app_id == app_id)
                .where(Webhook.created_at >= start_time)
                .group_by("time")
                .order_by("time")
            )
        except Exception:
            # SQLite fallback - use strftime
            time_series_result = await self.db.execute(
                select(
                    func.strftime(f"%Y-%m-%d %H:00" if bucket == "hour" else "%Y-%m-%d", Webhook.created_at).label("time"),
                    func.count(),
                )
                .where(Webhook.app_id == app_id)
                .where(Webhook.created_at >= start_time)
                .group_by("time")
                .order_by("time")
            )

        webhooks_over_time = [
            {"timestamp": str(ts), "count": count}
            for ts, count in time_series_result.all()
        ]

        # Top destinations (by delivery count)
        dest_result = await self.db.execute(
            select(
                Destination.name,
                func.count(Delivery.id).label("count"),
                func.sum(
                    case(
                        (Delivery.status == "success", 1),
                        else_=0,
                    )
                )
                / cast(func.count(Delivery.id), Float)
                * 100,
            )
            .join(Delivery, Delivery.destination_id == Destination.id)
            .join(Webhook, Webhook.id == Delivery.webhook_id)
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .group_by(Destination.name)
            .order_by(func.count(Delivery.id).desc())
            .limit(5)
        )
        top_destinations = [
            {"name": name, "count": count, "success_rate": rate}
            for name, count, rate in dest_result.all()
        ]

        return AnalyticsResponse(
            total_webhooks=total_webhooks,
            success_rate=round(success_rate, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            webhooks_by_status=webhooks_by_status,
            webhooks_over_time=webhooks_over_time,
            top_destinations=top_destinations,
        )
