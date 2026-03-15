"""Background worker for processing webhook delivery retries."""

import asyncio
import json
import logging
from datetime import datetime, UTC

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.config import settings
from hookflow.core.database import async_session_factory
from hookflow.core.queue import queue_client
from hookflow.models import Delivery
from hookflow.services import WebhookService

logger = logging.getLogger(__name__)


class RetryWorker:
    """Background worker that processes scheduled webhook retries."""

    def __init__(self, poll_interval: int = 5):
        """
        Args:
            poll_interval: Seconds between polling for retries due
        """
        self.poll_interval = poll_interval
        self.running = False
        self.worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the worker."""
        if self.running:
            logger.warning("Retry worker already running")
            return

        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        print(f"Retry worker started (poll interval: {self.poll_interval}s)")
        logger.info(f"Retry worker started (poll interval: {self.poll_interval}s)")

    async def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Retry worker stopped")

    async def _worker_loop(self) -> None:
        """Worker loop that polls for and processes retries."""
        logger.info("Retry worker loop started")

        while self.running:
            try:
                # Process all due retries
                processed = await self._process_due_retries()

                if processed > 0:
                    logger.info(f"Processed {processed} retry attempts")

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("Retry worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in retry worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Retry worker loop stopped")

    async def _process_due_retries(self) -> int:
        """Find and process all retries that are due.

        Returns:
            Number of retries processed
        """
        async with async_session_factory() as db:
            # Find deliveries ready for retry
            now = datetime.now(UTC)

            # Get deliveries that are retrying and due
            result = await db.execute(
                select(Delivery)
                .where(
                    Delivery.status == "retrying",
                    Delivery.retry_after <= now,
                )
                .limit(100)  # Process in batches
            )
            deliveries = list(result.scalars().all())

            if not deliveries:
                return 0

            processed = 0
            for delivery in deliveries:
                try:
                    # Increment attempt number and reset status
                    await db.execute(
                        update(Delivery)
                        .where(Delivery.id == delivery.id)
                        .values(
                            status="pending",
                            attempt_number=delivery.attempt_number + 1,
                            retry_after=None,
                        )
                    )
                    await db.commit()

                    # Re-enqueue for delivery
                    await queue_client.enqueue(
                        "webhook:delivery",
                        {
                            "webhook_id": str(delivery.webhook_id),
                            "destination_id": str(delivery.destination_id),
                        },
                    )

                    processed += 1
                    logger.info(
                        f"Re-queued delivery {delivery.id} "
                        f"(attempt {delivery.attempt_number + 1})"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to process retry for delivery {delivery.id}: {e}",
                        exc_info=True,
                    )
                    await db.rollback()

            return processed

    async def process_retry_queue_item(self, item: dict) -> None:
        """Process a retry item from the queue (alternative to polling).

        This allows retries to be triggered via the queue system
        with delays, instead of polling.

        Args:
            item: Queue item with webhook_id, destination_id, retry_after
        """
        webhook_id = item.get("webhook_id")
        destination_id = item.get("destination_id")
        retry_after_str = item.get("retry_after")

        if not webhook_id or not destination_id:
            logger.error(f"Invalid retry queue item: {item}")
            return

        async with async_session_factory() as db:
            # Find the delivery
            result = await db.execute(
                select(Delivery).where(
                    Delivery.webhook_id == webhook_id,
                    Delivery.destination_id == destination_id,
                    Delivery.status == "retrying",
                )
            )
            delivery = result.scalar_one_or_none()

            if not delivery:
                logger.warning(
                    f"No retrying delivery found for webhook={webhook_id}, "
                    f"destination={destination_id}"
                )
                return

            # Increment attempt and re-enqueue
            await db.execute(
                update(Delivery)
                .where(Delivery.id == delivery.id)
                .values(
                    status="pending",
                    attempt_number=delivery.attempt_number + 1,
                    retry_after=None,
                )
            )
            await db.commit()

            # Re-enqueue for delivery
            await queue_client.enqueue(
                "webhook:delivery",
                {
                    "webhook_id": webhook_id,
                    "destination_id": destination_id,
                },
            )

            logger.info(
                f"Re-queued delivery {delivery.id} via queue trigger "
                f"(attempt {delivery.attempt_number + 1})"
            )


# Global worker instance
_retry_worker: RetryWorker | None = None


async def start_retry_worker() -> None:
    """Start the global retry worker."""
    global _retry_worker
    if _retry_worker is None:
        _retry_worker = RetryWorker()
    await _retry_worker.start()


async def stop_retry_worker() -> None:
    """Stop the global retry worker."""
    global _retry_worker
    if _retry_worker:
        await _retry_worker.stop()
        _retry_worker = None


def get_retry_worker() -> RetryWorker | None:
    """Get the global retry worker instance."""
    return _retry_worker
