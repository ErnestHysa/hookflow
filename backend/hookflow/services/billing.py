"""Billing service for Stripe integration."""

import os
from datetime import datetime, timedelta
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.config import settings
from hookflow.models import PlanTier, User


class BillingError(Exception):
    """Error raised when billing operations fail."""

    pass


class StripeBillingService:
    """Service for managing Stripe subscriptions and billing."""

    # Price IDs for different plans (would be configured from environment)
    PRICES = {
        PlanTier.FREE: None,  # No price for free tier
        PlanTier.PRO: os.environ.get("STRIPE_PRICE_PRO", "price_pro_monthly"),
        PlanTier.TEAM: os.environ.get("STRIPE_PRICE_TEAM", "price_team_monthly"),
        PlanTier.ENTERPRISE: os.environ.get("STRIPE_PRICE_ENTERPRISE", "price_enterprise"),
    }

    # Features per plan
    FEATURES = {
        PlanTier.FREE: {
            "monthly_webhooks": 1_000,
            "retention_days": 7,
            "destinations": 1,
            "retry_attempts": 3,
        },
        PlanTier.PRO: {
            "monthly_webhooks": 50_000,
            "retention_days": 30,
            "destinations": 10,
            "retry_attempts": 5,
        },
        PlanTier.TEAM: {
            "monthly_webhooks": 500_000,
            "retention_days": 90,
            "destinations": 50,
            "retry_attempts": 10,
        },
        PlanTier.ENTERPRISE: {
            "monthly_webhooks": -1,  # Unlimited
            "retention_days": 365,
            "destinations": -1,  # Unlimited
            "retry_attempts": -1,  # Unlimited
        },
    }

    def __init__(self) -> None:
        if not settings.stripe_secret_key:
            raise BillingError("STRIPE_SECRET_KEY not configured")

        stripe.api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret

    async def create_customer(
        self,
        db: AsyncSession,
        user_id: str,
        email: str,
        name: str | None = None,
    ) -> stripe.Customer:
        """Create a Stripe customer for a user.

        Args:
            db: Database session
            user_id: User ID
            email: User email
            name: User name (optional)

        Returns:
            Stripe customer object

        Raises:
            BillingError: If customer creation fails
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id},
            )

            # Update user with customer ID
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                user.stripe_customer_id = customer.id
                await db.commit()

            return customer

        except stripe.error.StripeError as e:
            raise BillingError(f"Failed to create customer: {e}") from e

    async def create_subscription(
        self,
        db: AsyncSession,
        user_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> stripe.checkout.Session:
        """Create a checkout session for a subscription.

        Args:
            db: Database session
            user_id: User ID
            price_id: Stripe price ID
            success_url: URL to redirect to on success
            cancel_url: URL to redirect to on cancel

        Returns:
            Stripe checkout session

        Raises:
            BillingError: If session creation fails
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise BillingError("User not found")

        # Get or create Stripe customer
        customer_id = user.stripe_customer_id
        if not customer_id:
            customer = await self.create_customer(db, user_id, user.email, user.name)
            customer_id = customer.id

        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": user_id},
                subscription_data={
                    "metadata": {"user_id": user_id},
                },
            )

            return session

        except stripe.error.StripeError as e:
            raise BillingError(f"Failed to create checkout session: {e}") from e

    async def create_billing_portal_session(
        self,
        db: AsyncSession,
        user_id: str,
        return_url: str,
    ) -> stripe.billing_portal.Session:
        """Create a billing portal session for a user.

        Args:
            db: Database session
            user_id: User ID
            return_url: URL to redirect to after portal

        Returns:
            Stripe billing portal session

        Raises:
            BillingError: If session creation fails
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.stripe_customer_id:
            raise BillingError("User not found or no Stripe customer")

        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url,
            )

            return session

        except stripe.error.StripeError as e:
            raise BillingError(f"Failed to create portal session: {e}") from e

    async def cancel_subscription(
        self,
        db: AsyncSession,
        user_id: str,
        at_period_end: bool = True,
    ) -> stripe.Subscription:
        """Cancel a user's subscription.

        Args:
            db: Database session
            user_id: User ID
            at_period_end: If True, cancel at period end; otherwise immediately

        Returns:
            Cancelled subscription

        Raises:
            BillingError: If cancellation fails
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.stripe_subscription_id:
            raise BillingError("User not found or no active subscription")

        try:
            subscription = stripe.Subscription.modify(
                user.stripe_subscription_id,
                cancel_at_period_end=at_period_end,
            )

            return subscription

        except stripe.error.StripeError as e:
            raise BillingError(f"Failed to cancel subscription: {e}") from e

    def get_plan_from_price(self, price_id: str) -> PlanTier:
        """Determine plan tier from Stripe price ID.

        Args:
            price_id: Stripe price ID

        Returns:
            Plan tier

        Raises:
            BillingError: If price ID is unknown
        """
        for tier, price in self.PRICES.items():
            if price == price_id:
                return tier

        raise BillingError(f"Unknown price ID: {price_id}")

    def get_price_for_plan(self, plan: PlanTier) -> str | None:
        """Get Stripe price ID for a plan tier.

        Args:
            plan: Plan tier

        Returns:
            Stripe price ID or None for free tier
        """
        return self.PRICES.get(plan)

    def get_features_for_plan(self, plan: PlanTier) -> dict[str, int | bool]:
        """Get feature limits for a plan tier.

        Args:
            plan: Plan tier

        Returns:
            Dictionary of feature limits
        """
        return self.FEATURES.get(plan, self.FEATURES[PlanTier.FREE])

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload: dict[str, Any],
    ) -> None:
        """Handle a Stripe webhook event.

        Args:
            db: Database session
            payload: Webhook payload

        Raises:
            BillingError: If webhook processing fails
        """
        event_type = payload.get("type")
        data = payload.get("data", {})

        if event_type == "customer.created":
            await self._handle_customer_created(db, data)
        elif event_type == "customer.updated":
            await self._handle_customer_updated(db, data)
        elif event_type == "customer.subscription.created":
            await self._handle_subscription_created(db, data)
        elif event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(db, data)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(db, data)
        elif event_type == "invoice.paid":
            await self._handle_invoice_paid(db, data)
        elif event_type == "invoice.payment_failed":
            await self._handle_invoice_payment_failed(db, data)

    async def _handle_customer_created(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle customer.created event."""
        customer = data.get("object", {})
        user_id = customer.get("metadata", {}).get("user_id")

        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                user.stripe_customer_id = customer.get("id")
                await db.commit()

    async def _handle_customer_updated(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle customer.updated event."""
        # Handle customer updates (email, etc.)
        pass

    async def _handle_subscription_created(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle subscription.created event."""
        subscription = data.get("object", {})
        customer_id = subscription.get("customer")

        # Find user by customer ID
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.stripe_subscription_id = subscription.get("id")
            # Determine plan from price
            price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")

            try:
                plan = self.get_plan_from_price(price_id)
                user.plan_tier = plan
                await db.commit()
            except BillingError:
                # Unknown price, keep current plan
                pass

    async def _handle_subscription_updated(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle subscription.updated event."""
        subscription = data.get("object", {})
        customer_id = subscription.get("customer")

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Update subscription ID if changed
            user.stripe_subscription_id = subscription.get("id")

            # Check if subscription is canceled
            cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            if cancel_at_period_end:
                # Will be downgraded at period end
                pass

            # Update plan if price changed
            price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")

            try:
                plan = self.get_plan_from_price(price_id)
                user.plan_tier = plan
                await db.commit()
            except BillingError:
                pass

    async def _handle_subscription_deleted(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle subscription.deleted event."""
        subscription = data.get("object", {})
        customer_id = subscription.get("customer")

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.stripe_subscription_id = None
            user.plan_tier = PlanTier.FREE
            await db.commit()

    async def _handle_invoice_paid(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle invoice.paid event."""
        # Could track payment history, send receipts, etc.
        pass

    async def _handle_invoice_payment_failed(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle invoice.payment_failed event."""
        # Could send notification to user, retry logic, etc.
        subscription = data.get("subscription")
        if subscription:
            # Stripe automatically retries failed payments
            # Could add custom logic here
            pass

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify Stripe webhook signature.

        Args:
            payload: Raw request body
            signature: Stripe signature header

        Returns:
            True if signature is valid

        Raises:
            BillingError: If signature is invalid
        """
        if not self.webhook_secret:
            raise BillingError("STRIPE_WEBHOOK_SECRET not configured")

        try:
            stripe.WebhookSignature.verify_header(
                payload,
                signature,
                self.webhook_secret,
                int(os.environ.get("STRIPE_WEBHOOK_TOLERANCE", "300")),
            )
            return True

        except stripe.error.SignatureVerificationError as e:
            raise BillingError(f"Webhook signature verification failed: {e}") from e

    async def get_subscription_status(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> dict[str, Any]:
        """Get subscription status for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Subscription status dictionary
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "none", "plan": "free"}

        if not user.stripe_subscription_id:
            return {
                "status": "none" if user.plan_tier == PlanTier.FREE else "legacy",
                "plan": user.plan_tier,
            }

        try:
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)

            return {
                "status": subscription.get("status"),
                "plan": user.plan_tier,
                "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
                "current_period_end": subscription.get("current_period_end"),
            }

        except stripe.error.StripeError:
            return {"status": "unknown", "plan": user.plan_tier}


# Global service instance
_billing_service: StripeBillingService | None = None


def get_billing_service() -> StripeBillingService:
    """Get the global billing service instance."""
    global _billing_service
    if _billing_service is None and settings.stripe_secret_key:
        _billing_service = StripeBillingService()
    return _billing_service
