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
from hookflow.services.event_broadcaster import get_broadcaster
from hookflow.utils.retry import (
    RetryPolicy,
    calculate_backoff_with_retry_after,
    is_retryable_error,
)
from hookflow.utils.signature import (
    verify_signature_from_headers,
    WebhookSignatureError,
    generate_signature_headers,
)
from hookflow.services.rate_limit import RateLimitService, RateLimitExceededError


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

        # Check rate limit and increment counter
        rate_limit_service = RateLimitService(self.db)
        try:
            await rate_limit_service.check_and_increment(app_id, count=1)
        except RateLimitExceededError as e:
            # Convert to ValueError for consistency with existing error handling
            raise ValueError(
                f"Rate limit exceeded: {e.detail['current']}/{e.detail['limit']}. "
                f"Resets at {e.detail['reset_at']}"
            )

        # Verify signature if enabled
        if app.verify_signature and app.webhook_secret:
            try:
                payload = json.dumps(body)
                verify_signature_from_headers(
                    payload,
                    headers,
                    app.webhook_secret,
                )
            except WebhookSignatureError as e:
                raise ValueError(f"Invalid webhook signature: {e}")

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

        # Publish webhook received event
        broadcaster = get_broadcaster()
        await broadcaster.publish(
            f"app:{app_id}",
            {
                "type": "webhook.received",
                "data": {
                    "webhook_id": str(webhook.id),
                    "status": webhook.status,
                    "timestamp": webhook.created_at.isoformat(),
                },
            },
        )

        # Enqueue for processing
        await self._enqueue_webhook(webhook.id, app_id)

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

        # Create retry policy from destination config
        retry_policy = RetryPolicy(
            enabled=destination.retry_enabled,
            max_retries=destination.max_retries,
            base_ms=destination.retry_backoff_base_ms,
            max_ms=destination.retry_backoff_max_ms,
        )

        # Deliver based on type
        broadcaster = get_broadcaster()
        status_code = None
        exception_type = None

        try:
            result = await self._deliver_to_destination(webhook, destination)
            delivery.status = "success"
            delivery.response_status_code = result.get("status_code", 200)
            delivery.response_body = result.get("body", "")[:1000]
            delivery.response_time_ms = result.get("response_time_ms", 0)

            # Publish delivery success event
            await broadcaster.publish(
                f"app:{webhook.app_id}",
                {
                    "type": "delivery.success",
                    "data": {
                        "webhook_id": str(webhook_id),
                        "destination_id": str(destination_id),
                        "response_time_ms": result.get("response_time_ms", 0),
                    },
                },
            )
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            exception_type = type(e).__name__
            delivery.status = "failed"
            delivery.error_message = str(e)

            # Publish delivery failed event
            await broadcaster.publish(
                f"app:{webhook.app_id}",
                {
                    "type": "delivery.failed",
                    "data": {
                        "webhook_id": str(webhook_id),
                        "destination_id": str(destination_id),
                        "error": str(e),
                    },
                },
            )

            # Schedule retry if applicable
            if retry_policy.is_retryable_error(status_code, exception_type):
                if retry_policy.should_retry(delivery.attempt_number):
                    delivery.status = "retrying"
                    delivery.retry_after = retry_policy.calculate_next_retry(
                        delivery.attempt_number,
                        retry_after_header=None,  # Could extract from response headers
                    )
                    await self._enqueue_retry(
                        webhook_id,
                        destination_id,
                        delivery.retry_after,
                    )
                else:
                    # Max retries exceeded, mark as permanently failed
                    delivery.status = "failed"

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
        retry_after: datetime,
    ) -> None:
        """Enqueue delivery for retry at a specific time."""
        # Calculate delay in seconds for the queue
        delay_seconds = max(0, int((retry_after - datetime.utcnow()).total_seconds()))

        await queue_client.enqueue(
            "webhook:retry",
            {
                "webhook_id": str(webhook_id),
                "destination_id": str(destination_id),
                "retry_after": retry_after.isoformat(),
                "delay_seconds": delay_seconds,
            },
            delay=delay_seconds,
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
        elif destination.type == "telegram":
            return await self._deliver_telegram(webhook, destination)
        elif destination.type == "database":
            return await self._deliver_database(webhook, destination)
        elif destination.type == "email":
            return await self._deliver_email(webhook, destination)
        elif destination.type == "notion":
            return await self._deliver_notion(webhook, destination)
        elif destination.type == "airtable":
            return await self._deliver_airtable(webhook, destination)
        elif destination.type == "google_sheets":
            return await self._deliver_google_sheets(webhook, destination)
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

        # Get custom headers from destination config
        headers = destination.config.get("headers", {})

        # Apply transformation rules if present
        body = webhook.body
        if destination.transform_rules:
            body = self._apply_transform(body, destination.transform_rules)

        # Add webhook signature headers
        app = await self._get_app(webhook.app_id)
        if app and app.webhook_secret and app.verify_signature:
            payload = json.dumps(body)
            signature_headers = generate_signature_headers(
                payload,
                app.webhook_secret,
            )
            # Merge signature headers with custom headers
            # Signature headers should not override custom headers
            headers = {**signature_headers, **headers}

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

    async def _deliver_telegram(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to Telegram via Bot API."""

        import httpx
        import time

        bot_token = destination.config.get("bot_token")
        chat_id = destination.config.get("chat_id")

        if not bot_token or not chat_id:
            raise ValueError("Telegram destination missing bot_token or chat_id")

        # Format message for Telegram
        # Telegram messages have a 4096 character limit
        message = f"🔔 *Webhook Received*\n\n"
        message += f"📌 *App ID:* `{webhook.app_id[:8]}...`\n"
        message += f"🆔 *Webhook ID:* `{str(webhook.id)[:8]}...`\n"
        message += f"⏰ *Time:* {webhook.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"

        # Add event type if present
        body = webhook.body or {}
        if isinstance(body, dict):
            if "event" in body:
                message += f"📦 *Event:* `{body.get('event')}`\n"
            # Add a preview of the payload
            message += f"\n📄 *Payload Preview:*\n"
            message += "```json\n"
            payload_str = json.dumps(body, ensure_ascii=False)[:500]
            message += payload_str
            if len(json.dumps(body, ensure_ascii=False)) > 500:
                message += "..."
            message += "\n```"

        # Telegram Bot API URL
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
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

    async def _deliver_database(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to a database table."""
        from hookflow.integrations.database import deliver_database

        result = await deliver_database(webhook, destination, self.db)
        return {"status_code": 200, "body": str(result), "response_time_ms": 0}

    async def _deliver_email(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook via email."""
        from hookflow.integrations.email import deliver_email

        app = await self._get_app(webhook.app_id)
        app_name = app.name if app else "HookFlow"

        result = await deliver_email(webhook, destination, app_name)
        return {"status_code": 200, "body": str(result), "response_time_ms": 0}

    async def _deliver_notion(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to Notion database."""
        from hookflow.integrations.notion import deliver_notion
        import httpx
        import time

        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            start = time.time()
            result = await deliver_notion(webhook, destination, client)
            elapsed = (time.time() - start) * 1000

        return {
            "status_code": 200,
            "body": str(result),
            "response_time_ms": int(elapsed),
        }

    async def _deliver_airtable(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to Airtable table."""
        from hookflow.integrations.airtable import deliver_airtable
        import httpx
        import time

        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            start = time.time()
            result = await deliver_airtable(webhook, destination, client)
            elapsed = (time.time() - start) * 1000

        return {
            "status_code": 200,
            "body": str(result),
            "response_time_ms": int(elapsed),
        }

    async def _deliver_google_sheets(
        self,
        webhook: Webhook,
        destination: Destination,
    ) -> dict[str, Any]:
        """Deliver webhook to Google Sheets."""
        from hookflow.integrations.google_sheets import deliver_google_sheets
        import time

        start = time.time()
        result = await deliver_google_sheets(webhook, destination)
        elapsed = (time.time() - start) * 1000

        return {
            "status_code": 200,
            "body": str(result),
            "response_time_ms": int(elapsed),
        }

    def _apply_transform(self, body: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
        """Apply transformation rules to webhook body.

        Supported transformation rules:
        - events: Filter by event type (skip if not matching)
        - filter_values: Filter based on field values (conditional filtering)
        - extract: Extract specific fields using JSONPath-like syntax
        - filter: Keep only specified keys
        - remove: Remove specific fields
        - flatten: Flatten nested structures
        - rename: Rename fields
        - add: Add static fields
        - map: Map field values through a lookup table
        - cast: Cast field values to different types

        Processing order:
        1. events (event type filtering)
        2. filter_values (conditional filtering)
        3. extract (field extraction)
        4. filter/remove (key filtering)
        5. flatten (structure flattening)
        6. rename (field renaming)
        7. map (value mapping)
        8. cast (type casting)
        9. add (add static fields)
        """

        result = body.copy()

        # Event type filtering - skip transformation if event doesn't match
        if "events" in rules:
            allowed_events = rules["events"]
            if isinstance(allowed_events, list):
                event_type = self._extract_jsonpath(body, "event") or self._extract_jsonpath(body, "type")
                if event_type not in allowed_events:
                    # Return empty dict to signal that this webhook should be skipped
                    return {}

        # Conditional filtering based on field values (check original body)
        if "filter_values" in rules:
            if not self._matches_filter_values(body, rules["filter_values"]):
                # Webhook doesn't match filter conditions, skip it
                return {}

        # JSONPath extraction
        if "extract" in rules:
            extract = rules["extract"]
            if isinstance(extract, dict):
                result = {}
                for key, path in extract.items():
                    result[key] = self._extract_jsonpath(body, path)

        # Key filtering (keep only specified keys)
        if "filter" in rules:
            keep = rules["filter"]
            if isinstance(keep, list):
                result = {k: v for k, v in result.items() if k in keep}

        # Remove specific fields
        if "remove" in rules:
            remove_fields = rules["remove"]
            if isinstance(remove_fields, list):
                for field in remove_fields:
                    result.pop(field, None)

        # Flattening
        if "flatten" in rules and rules["flatten"]:
            result = self._flatten_dict(result)

        # Renaming
        if "rename" in rules:
            for old_key, new_key in rules["rename"].items():
                if old_key in result:
                    result[new_key] = result.pop(old_key)

        # Value mapping
        if "map" in rules:
            for field, mapping in rules["map"].items():
                if field in result and isinstance(mapping, dict):
                    original_value = result[field]
                    if original_value in mapping:
                        result[field] = mapping[original_value]

        # Type casting
        if "cast" in rules:
            for field, target_type in rules["cast"].items():
                if field in result:
                    result[field] = self._cast_value(result[field], target_type)

        # Add static fields (last, so they can't be affected by other transforms)
        if "add" in rules:
            add_fields = rules["add"]
            if isinstance(add_fields, dict):
                for key, value in add_fields.items():
                    result[key] = value

        return result

    def _matches_filter_values(self, data: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if data matches all filter conditions.

        Args:
            data: The data to check
            filters: Dictionary of field -> expected value or condition
                     Conditions can be:
                     - Simple value: matches if data[field] == value
                     - Dict with operators: {"$eq": value}, {"$ne": value},
                       {"$in": [values]}, {"$nin": [values]},
                       {"$exists": bool}, {"$gt": number}, {"$lt": number}

        Returns:
            True if all filters match
        """
        for field, condition in filters.items():
            value = self._extract_jsonpath(data, field)

            if isinstance(condition, dict):
                # Operator-based condition
                for op, expected in condition.items():
                    if op == "$eq":
                        if value != expected:
                            return False
                    elif op == "$ne":
                        if value == expected:
                            return False
                    elif op == "$in":
                        if value not in expected:
                            return False
                    elif op == "$nin":
                        if value in expected:
                            return False
                    elif op == "$exists":
                        if (value is None) == expected:
                            return False
                    elif op == "$gt":
                        try:
                            if float(value) <= float(expected):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "$lt":
                        try:
                            if float(value) >= float(expected):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "$gte":
                        try:
                            if float(value) < float(expected):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "$lte":
                        try:
                            if float(value) > float(expected):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "$contains":
                        if expected not in str(value):
                            return False
                    elif op == "$regex":
                        import re
                        if not re.match(expected, str(value)):
                            return False
            else:
                # Simple equality check
                if value != condition:
                    return False

        return True

    def _cast_value(self, value: Any, target_type: str) -> Any:
        """Cast a value to the specified type.

        Args:
            value: The value to cast
            target_type: The target type (string, int, float, bool, json)

        Returns:
            The casted value
        """
        if value is None:
            return None

        try:
            if target_type == "string":
                return str(value)
            elif target_type == "int":
                return int(float(value)) if isinstance(value, str) else int(value)
            elif target_type == "float":
                return float(value)
            elif target_type == "bool":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "on")
                return bool(value)
            elif target_type == "json":
                if isinstance(value, str):
                    import json
                    return json.loads(value)
                return value
            else:
                return value
        except (ValueError, TypeError, json.JSONDecodeError):
            return value

    def _extract_jsonpath(self, data: dict[str, Any], path: str) -> Any:
        """Extract value using JSONPath-like syntax.

        Supports:
        - Dot notation: "user.name"
        - Array access: "items.0" or "items[0]"
        - Wildcards: "users.*.name" (gets first match)

        Args:
            data: The data to extract from
            path: The JSONPath-like expression

        Returns:
            The extracted value or None if not found
        """
        if not data or not path:
            return None

        # Handle array notation [index]
        path = path.replace("[", ".").replace("]", "")

        keys = path.split(".")
        result = data

        i = 0
        while i < len(keys):
            key = keys[i]
            if not key:
                i += 1
                continue

            if result is None:
                return None

            if isinstance(result, dict):
                result = result.get(key)
                i += 1
            elif isinstance(result, list):
                if key == "*":
                    # Wildcard for array
                    # Check if the next key exists (e.g., "users.*.name")
                    if i + 1 < len(keys):
                        next_key = keys[i + 1]
                        # For each item in the array, get the next_key value
                        # Return the first non-null match
                        for item in result:
                            if isinstance(item, dict) and next_key in item:
                                result = item.get(next_key)
                                i += 2  # Skip both * and the next key
                                break
                        else:
                            return None
                    else:
                        # Just *, return the first item
                        result = result[0] if result else None
                        i += 1
                elif key.isdigit():
                    idx = int(key)
                    result = result[idx] if 0 <= idx < len(result) else None
                    i += 1
                else:
                    # Access property on array items - return first matching value
                    for item in result:
                        if isinstance(item, dict) and key in item:
                            result = item.get(key)
                            break
                    else:
                        return None
                    i += 1
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

        # Get all deliveries with their destinations
        result = await self.db.execute(
            select(Delivery)
            .where(Delivery.webhook_id == webhook_id)
        )
        deliveries = list(result.scalars().all())

        if not deliveries:
            return

        # Check if each delivery is complete
        all_complete = True
        for delivery in deliveries:
            if delivery.status == "success":
                continue

            # Get destination to check max retries
            dest_result = await self.db.execute(
                select(Destination).where(Destination.id == delivery.destination_id)
            )
            destination = dest_result.scalar_one_or_none()

            max_retries = destination.max_retries if destination else 3

            # Complete if: success, or failed after max retries
            if delivery.status == "failed" and delivery.attempt_number >= max_retries + 1:
                continue

            # Still pending or retrying
            all_complete = False
            break

        if all_complete:
            webhook.status = WebhookStatus.COMPLETED
            await self.db.commit()
