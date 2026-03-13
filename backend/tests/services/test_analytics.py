import pytest
from datetime import datetime, timedelta
from hookflow.services.analytics import AnalyticsService
from hookflow.models.app import App, Webhook, Delivery
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_analytics_no_webhooks(db_session: AsyncSession):
    """Test analytics when app has no webhooks"""
    app = App(
        id="test-app-1",
        name="Test App",
        user_id="test-user-1",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    service = AnalyticsService(db_session)
    analytics = await service.get_analytics(app.id)

    assert analytics.total_webhooks == 0
    assert analytics.success_rate == 0.0
    assert analytics.webhooks_by_status == {}


@pytest.mark.asyncio
async def test_get_analytics_with_webhooks(db_session: AsyncSession):
    """Test analytics with sample webhooks"""
    app = App(
        id="test-app-2",
        name="Test App 2",
        user_id="test-user-2",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    # Create test webhooks
    now = datetime.utcnow()

    # Success webhook
    webhook1 = Webhook(
        id="webhook-1",
        app_id=app.id,
        status="completed",
        body={"test": "data"},
        created_at=now,
    )
    db_session.add(webhook1)

    # Failed webhook
    webhook2 = Webhook(
        id="webhook-2",
        app_id=app.id,
        status="failed",
        body={"test": "data2"},
        created_at=now - timedelta(hours=1),
    )
    db_session.add(webhook2)

    await db_session.commit()
    await db_session.refresh(webhook1)
    await db_session.refresh(webhook2)

    # Create a destination first (required by Delivery foreign key)
    from hookflow.models.app import Destination
    dest = Destination(
        id="dest-1",
        app_id=app.id,
        name="Test Destination",
        type="http",
        config={"url": "https://example.com"}
    )
    db_session.add(dest)
    await db_session.commit()

    # Create deliveries
    delivery1 = Delivery(
        id="delivery-1",
        webhook_id=webhook1.id,
        destination_id=dest.id,
        status="success",
        response_status_code=200,
        response_time_ms=150,
        attempt_number=1,
    )
    db_session.add(delivery1)

    delivery2 = Delivery(
        id="delivery-2",
        webhook_id=webhook2.id,
        destination_id=dest.id,
        status="failed",
        response_status_code=500,
        attempt_number=1,
    )
    db_session.add(delivery2)

    await db_session.commit()

    service = AnalyticsService(db_session)
    analytics = await service.get_analytics(app.id)

    assert analytics.total_webhooks == 2
    assert analytics.success_rate == 50.0  # 1 success out of 2
    assert analytics.webhooks_by_status.get("completed", 0) == 1
    assert analytics.webhooks_by_status.get("failed", 0) == 1


@pytest.mark.asyncio
async def test_get_analytics_response_time_calculation(db_session: AsyncSession):
    """Test average response time calculation"""
    app = App(
        id="test-app-3",
        name="Test App 3",
        user_id="test-user-3",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    # Create webhook with successful delivery
    webhook = Webhook(
        id="webhook-3",
        app_id=app.id,
        status="completed",
        body={"test": "data"},
    )
    db_session.add(webhook)
    await db_session.commit()
    await db_session.refresh(webhook)

    # Create a destination first
    from hookflow.models.app import Destination
    dest = Destination(
        id="dest-1",
        app_id=app.id,
        name="Test Destination",
        type="http",
        config={"url": "https://example.com"}
    )
    db_session.add(dest)
    await db_session.commit()

    # Create deliveries with different response times
    for i, response_time in enumerate([100, 200, 300]):
        delivery = Delivery(
            id=f"delivery-{i}",
            webhook_id=webhook.id,
            destination_id=dest.id,
            status="success",
            response_status_code=200,
            response_time_ms=response_time,
            attempt_number=1,
        )
        db_session.add(delivery)

    await db_session.commit()

    service = AnalyticsService(db_session)
    analytics = await service.get_analytics(app.id)

    assert analytics.avg_response_time_ms == 200.0  # (100 + 200 + 300) / 3
