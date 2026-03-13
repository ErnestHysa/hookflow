"""Tests for Stripe billing service."""

import pytest
from hookflow.services.billing import BillingError, StripeBillingService, get_billing_service


class TestStripeBillingService:
    """Tests for StripeBillingService."""

    def test_get_singleton_without_config(self, monkeypatch):
        """Test that get_billing_service returns None without config."""
        from hookflow.core.config import settings

        monkeypatch.setattr(settings, "stripe_secret_key", None)

        service = get_billing_service()
        assert service is None

    def test_service_init_without_secret_key(self, monkeypatch):
        """Test service initialization fails without secret key."""
        from hookflow.core.config import settings

        monkeypatch.setattr(settings, "stripe_secret_key", None)

        with pytest.raises(BillingError, match="STRIPE_SECRET_KEY not configured"):
            StripeBillingService()

    def test_get_plan_from_price_unknown_price(self, monkeypatch):
        """Test getting plan from unknown price ID."""
        from hookflow.core.config import settings

        monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

        service = StripeBillingService()

        with pytest.raises(BillingError, match="Unknown price ID"):
            service.get_plan_from_price("price_unknown")

    def test_get_features_for_plan(self, monkeypatch):
        """Test getting features for different plan tiers."""
        from hookflow.core.config import settings
        from hookflow.models import PlanTier

        monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

        service = StripeBillingService()

        # Free tier features
        free_features = service.get_features_for_plan(PlanTier.FREE)
        assert free_features["monthly_webhooks"] == 1_000
        assert free_features["retention_days"] == 7
        assert free_features["destinations"] == 1

        # Pro tier features
        pro_features = service.get_features_for_plan(PlanTier.PRO)
        assert pro_features["monthly_webhooks"] == 50_000
        assert pro_features["retention_days"] == 30
        assert pro_features["destinations"] == 10

        # Enterprise tier features (unlimited)
        enterprise_features = service.get_features_for_plan(PlanTier.ENTERPRISE)
        assert enterprise_features["monthly_webhooks"] == -1
        assert enterprise_features["destinations"] == -1

    def test_get_price_for_plan(self, monkeypatch):
        """Test getting price ID for plan tier."""
        from hookflow.core.config import settings
        from hookflow.models import PlanTier

        monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

        service = StripeBillingService()

        # Free tier has no price
        assert service.get_price_for_plan(PlanTier.FREE) is None

        # Other tiers return price IDs (from env or defaults)
        pro_price = service.get_price_for_plan(PlanTier.PRO)
        assert pro_price is not None


@pytest.mark.asyncio
async def test_get_subscription_status_no_user(db_session, monkeypatch):
    """Test getting subscription status for non-existent user."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

    service = StripeBillingService()

    status = await service.get_subscription_status(db_session, "nonexistent_user")

    assert status["status"] == "none"
    assert status["plan"] == "free"


@pytest.mark.asyncio
async def test_get_subscription_status_free_user(db_session, monkeypatch):
    """Test getting subscription status for free tier user."""
    from hookflow.core.config import settings
    from hookflow.models import PlanTier, User

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

    # Create free tier user
    user = User(
        id="free_user_123",
        email="free@example.com",
        name="Free User",
        password_hash="hash",
        plan_tier=PlanTier.FREE,
    )
    db_session.add(user)
    await db_session.commit()

    service = StripeBillingService()
    status = await service.get_subscription_status(db_session, "free_user_123")

    assert status["status"] == "none"
    assert status["plan"] == "free"


@pytest.mark.asyncio
async def test_handle_customer_created_webhook(db_session, monkeypatch):
    """Test handling customer.created webhook event."""
    from hookflow.core.config import settings
    from hookflow.models import User

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

    # Create user first
    user = User(
        id="customer_user_123",
        email="customer@example.com",
        name="Customer User",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    service = StripeBillingService()

    payload = {
        "type": "customer.created",
        "data": {
            "object": {
                "id": "cus_test_123",
                "email": "customer@example.com",
                "metadata": {"user_id": "customer_user_123"},
            }
        },
    }

    await service.handle_webhook(db_session, payload)

    # Verify customer ID was saved
    await db_session.refresh(user)
    assert user.stripe_customer_id == "cus_test_123"


@pytest.mark.asyncio
async def test_handle_subscription_deleted_webhook(db_session, monkeypatch):
    """Test handling subscription.deleted webhook event."""
    from hookflow.core.config import settings
    from hookflow.models import PlanTier, User

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")

    # Create user with subscription
    user = User(
        id="sub_user_123",
        email="sub@example.com",
        name="Sub User",
        password_hash="hash",
        plan_tier=PlanTier.PRO,
        stripe_customer_id="cus_test_456",
        stripe_subscription_id="sub_test_789",
    )
    db_session.add(user)
    await db_session.commit()

    service = StripeBillingService()

    payload = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test_789",
                "customer": "cus_test_456",
            }
        },
    }

    await service.handle_webhook(db_session, payload)

    # Verify subscription was cleared and user downgraded
    await db_session.refresh(user)
    assert user.stripe_subscription_id is None
    assert user.plan_tier == PlanTier.FREE
