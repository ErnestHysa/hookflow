"""Background worker for processing webhook deliveries."""

import asyncio
import json
import logging

from hookflow.core.config import settings
from hookflow.core.database import async_session_factory
from hookflow.core.queue import queue_client
from hookflow.services import WebhookService

logger = logging.getLogger(__name__)


class DeliveryWorker:
    """Background worker that processes webhook deliveries from the queue."""

    def __init__(self, queue_name: str = "webhook:delivery"):
        self.queue_name = queue_name
        self.running = False
        self.worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the worker."""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        print(f"Delivery worker started for queue: {self.queue_name}")
        logger.info(f"Delivery worker started for queue: {self.queue_name}")

    async def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Delivery worker stopped")

    async def _worker_loop(self) -> None:
        """Worker loop that processes items from the queue."""
        logger.info("Worker loop started")

        while self.running:
            try:
                # Dequeue item with timeout
                item = await queue_client.dequeue(self.queue_name, timeout=1)

                if item is None:
                    # No items, wait a bit
                    await asyncio.sleep(0.1)
                    continue

                # Parse the item
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse queue item: {e}")
                        continue

                # Process the delivery
                webhook_id = item.get("webhook_id")
                destination_id = item.get("destination_id")

                if not webhook_id or not destination_id:
                    logger.error(f"Invalid queue item: {item}")
                    continue

                logger.info(f"Processing delivery: webhook={webhook_id}, destination={destination_id}")

                # Process in a separate session
                async with async_session_factory() as db:
                    service = WebhookService(db)
                    try:
                        await service.deliver_webhook(webhook_id, destination_id)
                        logger.info(f"Delivery successful: webhook={webhook_id}, destination={destination_id}")
                    except Exception as e:
                        logger.error(f"Delivery failed: webhook={webhook_id}, destination={destination_id}, error={e}")

            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Worker loop stopped")


# Global worker instance
_worker: DeliveryWorker | None = None


async def start_worker() -> None:
    """Start the global delivery worker."""
    global _worker
    if _worker is None:
        _worker = DeliveryWorker()
    await _worker.start()


async def stop_worker() -> None:
    """Stop the global delivery worker."""
    global _worker
    if _worker:
        await _worker.stop()
        _worker = None


def get_worker() -> DeliveryWorker | None:
    """Get the global delivery worker instance."""
    return _worker
