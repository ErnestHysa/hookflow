"""Webhook processing service."""

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from hookflow.core.config import settings
from hookflow.core.queue import queue_client
from hookflow.models import App, Delivery, Destination, Webhook
from hookflow.schemas import WebhookStatus


class WebhookService:
    """Service for processing webhooks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def receive_webhook(
        self,
        app_id: str,
        body: dict[str, Any],
        headers: dict[str, str],
        source_ip: str | None = None,
    ) -> Webhook:
        """Receive and store a webhook event."""

        # Get app
        app = await self._get_app(app_id)
        if not app:
            raise ValueError(f"App {app_id} not found")

        # Check rate limit
        await self._check_rate_limit(app)

        # Verify signature if enabled
        if app.verify_signature:
            signature = headers.get("x-webhook-signature", "")
            if not self._verify_signature(body, signature, app.webhook_secret):
                raise ValueError("Invalid webhook signature")

        # Check idempotency
        idempotency_key = headers.get("x-idempotency-key")
        if idempotency_key:
            existing = await self._get_webhook_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        # Create webhook record
        webhook = Webhook(
            app_id=app_id,
            idempotency_key=idempotency_key,
            source_ip=source_ip,
            user_agent=headers.get("user-agent"),
            content_type=headers.get("content-type", "application/json"),
            headers=headers,
            body=body,
            status=WebhookStatus.PENDING,
        )

        self.db.add(webhook)
        await self.db.commit()
        await self.db.refresh(webhook)

        # Enqueue for processing
        await self._enqueue_webhook(webhook.id, app_id)

        # Update app counter
        app.current_month_count += 1
        await self.db.commit()

        return webhook

    async def process_webhook(self, webhook_id: str) -> None:
        """Process a webhook and deliver to destinations."""

        webhook = await self._get_webhook(webhook_id)
        if not webhook:
            raise ValueError(f"Webhook {webhook_id} not found")

        if webhook.status != WebhookStatus.PENDING:
            return  # Already processed

        webhook.status = WebhookStatus.PROCESSING
        await self.db.commit()

        # Get active destinations
        destinations = await self._get_destinations(webhook.app_id)

        if not destinations:
            webhook.status = WebhookStatus.COMPLETED
            await self.db.commit()
            return

        # Create delivery attempts
        for destination in destinations:
            delivery = Delivery(
                webhook_id=webhook_id,
                destination_id=destination.id,
                attempt_number=1,
                status="pending",
            )
            self.db.add(delivery)

        await self.db.commit()

        # Enqueue deliveries for processing
        for destination in destinations:
            await self._enqueue_delivery(webhook_id, destination.id)

    async def deliver_webhook(
        self,
        webhook_id: str,
        destination_id: str,
    ) -> Delivery:
        """Deliver webhook to a destination."""

        webhook = await self._get_webhook(webhook_id)
        destination = await self._get_destination(destination_id)

        if not webhook or not destination:
            raise ValueError("Webhook or destination not found")

        # Get pending delivery
        delivery = await self._get_pending_delivery(webhook_id, destination_id)
        if not delivery:
            raise ValueError("No pending delivery found")

        # Deliver based on type
        try:
            result = await self._deliver_to_destination(webhook, destination)
            delivery.status = "success"
            delivery.response_status_code = result.get("status_code", 200)
            delivery.response_body = result.get("body", "")[:1000]
            delivery.response_time_ms = result.get("response_time_ms", 0)
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)

            # Schedule retry if applicable
            if delivery.attempt_number < settings.webhook_max_retries:
                delivery.status = "retrying"
                delay = settings.webhook_retry_delay * (2 ** (delivery.attempt_number - 1))
                delivery.retry_after = datetime.utcnow() + timedelta(seconds=delay)
                await self._enqueue_retry(webhook_id, destination_id, delay)

        await self.db.commit()
        await self.db.refresh(delivery)

        # Check if webhook is complete
        await self._check_webhook_completion(webhook_id)

        return delivery

    async def replay_webhook(
        self,
        webhook_id: str,
        destination_ids: list[uuid.UUID] | None = None,
    ) -> list[Delivery]:
        """Replay a webhook to destinations."""

        webhook = await self._get_webhook(webhook_id)
        if not webhook:
            raise ValueError(f"Webhook {webhook_id} not found")

        # Get destinations
        if destination_ids:
            destinations = [
                await self._get_destination(str(dest_id))
                for dest_id in destination_ids
            ]
            # Filter out None values (invalid destination IDs)
            destinations = [d for d in destinations if d is not None]
        else:
            destinations = await self._get_destinations(webhook.app_id)

        if not destinations:
            raise ValueError("No valid destinations found")

        deliveries = []
        for destination in destinations:
            delivery = Delivery(
                webhook_id=webhook_id,
                destination_id=destination.id,
                attempt_number=1,
                status="pending",
            )
            self.db.add(delivery)
            await self.db.commit()
            await self.db.refresh(delivery)

            await self._enqueue_delivery(webhook_id, destination.id)
            deliveries.append(delivery)

        return deliveries

    async def get_webhooks(
        self,
        app_id: str,
        limit: int = 100,
        offset: int = 0,
        status: WebhookStatus | None = None,
    ) -> tuple[list[Webhook], int]:
        """Get webhooks for an app."""

        query = select(Webhook).where(Webhook.app_id == app_id)

        if status:
            query = query.where(Webhook.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.order_by(Webhook.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        webhooks = list(result.scalars().all())

        return webhooks, total

    async def get_webhook_detail(self, webhook_id: str) -> tuple[Webhook | None, list[Delivery]]:
        """Get webhook with delivery details."""

        webhook = await self._get_webhook(webhook_id)
        deliveries = []
        if webhook:
            # Load deliveries separately to avoid relationship issues
            result = await self.db.execute(
                select(Delivery)
                .where(Delivery.webhook_id == webhook_id)
                .order_by(Delivery.created_at.desc())
            )
            deliveries = list(result.scalars().all())

        return webhook, deliveries

    # Helper methods

    async def _get_app(self, app_id: str) -> App | None:
        result = await self.db.execute(select(App).where(App.id == app_id))
        return result.scalar_one_or_none()

    async def _get_webhook(self, webhook_id: str) -> Webhook | None:
        result = await self.db.execute(select(Webhook).where(Webhook.id == webhook_id))
        return result.scalar_one_or_none()

    async def _get_destination(self, destination_id: str) -> Destination | None:
        result = await self.db.execute(
            select(Destination).where(Destination.id == destination_id)
        )
        return result.scalar_one_or_none()

    async def _get_webhook_by_idempotency_key(self, key: str) -> Webhook | None:
        result = await self.db.execute(
            select(Webhook).where(Webhook.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def _get_destinations(
        self,
        app_id: str,
    ) -> list[Destination]:
        result = await self.db.execute(
            select(Destination).where(
                and_(Destination.app_id == app_id, Destination.is_active == True)
            )
        )
        return list(result.scalars().all())

    async def _get_pending_delivery(
        self,
        webhook_id: str,
        destination_id: str,
    ) -> Delivery | None:
        result = await self.db.execute(
            select(Delivery).where(
                and_(
                    Delivery.webhook_id == webhook_id,
                    Delivery.destination_id == destination_id,
                    Delivery.status == "pending",
                )
            )
        )
        return result.scalar_one_or_none()

    def _verify_signature(
        self,
        body: dict[str, Any],
        signature: str,
        secret: str,
    ) -> bool:
        """Verify HMAC signature."""

        if not signature:
            return False

        # Parse signature (format: sha256=hash)
        try:
            algorithm, received_hash = signature.split("=", 1)
        except ValueError:
            return False

        if algorithm != "sha256":
            return False

        # Compute expected hash
        payload = json.dumps(body, separators=(",", ":"), sort_keys=True)
        expected_hash = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(received_hash, expected_hash)

    async def _check_rate_limit(self, app: App) -> None:
        """Check if app is within rate limit."""

        key = f"ratelimit:{app.id}:{datetime.utcnow().strftime('%Y-%m')}"
        allowed, current = await queue_client.incr_limit(
            key=key,
            limit=app.monthly_limit,
            window=60 * 60 * 24 * 30,  # 30 days
        )

        if not allowed:
            raise ValueError(f"Rate limit exceeded: {current}/{app.monthly_limit}")

    async def _enqueue_webhook(self, webhook_id: str, app_id: str) -> None:
        """Enqueue webhook for processing."""
        await queue_client.enqueue(
            "webhook:processing",
            {"webhook_id": str(webhook_id), "app_id": str(app_id)},
        )

    async def _enqueue_delivery(
        self,
        webhook_id: str,
        destination_id: str,
    ) -> None:
        """Enqueue delivery for processing."""
        await queue_client.enqueue(
            "webhook:delivery",
            {"webhook_id": str(webhook_id), "destination_id": str(destination_id)},
        )

    async def _enqueue_retry(
        self,
        webhook_id: str,
        destination_id: str,
        delay_seconds: int,
    ) -> None:
        """Enqueue delivery for retry."""
        # For in-memory queue, just enqueue immediately with retry info
        # In production with Redis, would use sorted set for scheduling
        await queue_client.enqueue(
            "webhook:retry",
            {
                "webhook_id": str(webhook_id),
                "destination_id": str(destination_id),
                "retry_after": (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat(),
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _deliver_to_destination(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to destination based on type."""

        if destination.type == "http":
            return await self._deliver_http(webhook, destination)
        elif destination.type == "slack":
            return await self._deliver_slack(webhook, destination)
        elif destination.type == "discord":
            return await self._deliver_discord(webhook, destination)
        else:
            raise ValueError(f"Unsupported destination type: {destination.type}")

    async def _deliver_http(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to HTTP endpoint."""

        import httpx
        import time

        url = destination.config.get("url")
        if not url:
            raise ValueError("HTTP destination missing URL")

        headers = destination.config.get("headers", {})

        # Apply transformation rules if present
        body = webhook.body
        if destination.transform_rules:
            body = self._apply_transform(body, destination.transform_rules)

        start = time.time()
        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            response = await client.post(
                url,
                json=body,
                headers=headers,
            )
        elapsed = (time.time() - start) * 1000

        response.raise_for_status()

        return {
            "status_code": response.status_code,
            "body": response.text[:1000],
            "response_time_ms": int(elapsed),
        }

    async def _deliver_slack(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to Slack webhook URL."""

        import httpx
        import time

        url = destination.config.get("webhook_url")
        if not url:
            raise ValueError("Slack destination missing webhook_url")

        # Format for Slack
        payload = {
            "text": f"Webhook received from app {webhook.app_id}",
            "attachments": [
                {
                    "color": "good" if webhook.status == "completed" else "warning",
                    "fields": [
                        {"title": "Webhook ID", "value": str(webhook.id), "short": True},
                        {
                            "title": "Timestamp",
                            "value": webhook.created_at.isoformat(),
                            "short": True,
                        },
                    ],
                }
            ],
        }

        start = time.time()
        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            response = await client.post(url, json=payload)
        elapsed = (time.time() - start) * 1000

        response.raise_for_status()

        return {
            "status_code": response.status_code,
            "body": response.text[:1000],
            "response_time_ms": int(elapsed),
        }

    async def _deliver_discord(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to Discord webhook URL."""

        import httpx
        import time

        url = destination.config.get("webhook_url")
        if not url:
            raise ValueError("Discord destination missing webhook_url")

        # Format for Discord
        payload = {
            "embeds": [
                {
                    "title": "Webhook Received",
                    "fields": [
                        {"name": "Webhook ID", "value": str(webhook.id)},
                        {"name": "Status", "value": webhook.status},
                    ],
                    "timestamp": webhook.created_at.isoformat(),
                }
            ]
        }

        start = time.time()
        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            response = await client.post(url, json=payload)
        elapsed = (time.time() - start) * 1000

        response.raise_for_status()

        return {
            "status_code": response.status_code,
            "body": response.text[:1000],
            "response_time_ms": int(elapsed),
        }

    def _apply_transform(self, body: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
        """Apply transformation rules to webhook body."""

        result = body.copy()

        # JSONPath extraction
        if "extract" in rules:
            extract = rules["extract"]
            if isinstance(extract, dict):
                result = {}
                for key, path in extract.items():
                    result[key] = self._extract_jsonpath(body, path)

        # Filtering
        if "filter" in rules:
            keep = rules["filter"]
            if isinstance(keep, list):
                result = {k: v for k, v in result.items() if k in keep}

        # Flattening
        if "flatten" in rules and rules["flatten"]:
            result = self._flatten_dict(result)

        # Renaming
        if "rename" in rules:
            for old_key, new_key in rules["rename"].items():
                if old_key in result:
                    result[new_key] = result.pop(old_key)

        return result

    def _extract_jsonpath(self, data: dict[str, Any], path: str) -> Any:
        """Extract value using JSONPath-like syntax."""
        keys = path.split(".")
        result = data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
            elif isinstance(result, list) and key.isdigit():
                result = result[int(key)]
            else:
                return None
        return result

    def _flatten_dict(self, data: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
        """Flatten nested dictionary."""

        items = []
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            if isinstance(value, dict):
                items.extend(self._flatten_dict(value, new_key, sep=sep).items())
            else:
                items.append((new_key, value))
        return dict(items)

    async def _check_webhook_completion(self, webhook_id: str) -> None:
        """Check if all deliveries are complete and update webhook status."""

        webhook = await self._get_webhook(webhook_id)
        if not webhook:
            return

        # Get all deliveries
        result = await self.db.execute(
            select(Delivery).where(Delivery.webhook_id == webhook_id)
        )
        deliveries = list(result.scalars().all())

        if not deliveries:
            return

        # Check if all are complete (success or failed after max retries)
        all_complete = all(
            d.status == "success"
            or (d.status == "failed" and d.attempt_number >= settings.webhook_max_retries)
            for d in deliveries
        )

        if all_complete:
            webhook.status = WebhookStatus.COMPLETED
            await self.db.commit()
