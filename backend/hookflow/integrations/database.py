"""Database destination integration - stores webhooks in a database table."""

import json
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models.app import Webhook, Destination
from hookflow.core.database import get_db


class DatabaseDestination:
    """Delivers webhooks to a database table."""

    def __init__(self, db: AsyncSession, destination: Destination):
        self.db = db
        self.destination = destination
        self.config = destination.config or {}

    async def deliver(self, webhook: Webhook) -> dict[str, Any]:
        """
        Deliver webhook payload to a database table.

        Creates the table if it doesn't exist and inserts the webhook data.
        """
        table_name = self.config.get("table_name") or f"webhooks_{webhook.app_id}"
        create_table = self.config.get("create_table", True)

        # Create table if requested
        if create_table:
            await self._create_table(table_name)

        # Insert webhook data
        await self._insert_webhook(table_name, webhook)

        return {
            "table_name": table_name,
            "rows_inserted": 1,
        }

    async def _create_table(self, table_name: str) -> None:
        """Create the destination table if it doesn't exist."""
        create_sql = text(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                webhook_id UUID NOT NULL,
                app_id UUID NOT NULL,
                body JSONB NOT NULL,
                headers JSONB,
                source_ip VARCHAR(45),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_{table_name.replace('-', '_')}_webhook_id ON {table_name}(webhook_id);
            CREATE INDEX IF NOT EXISTS idx_{table_name.replace('-', '_')}_created_at ON {table_name}(created_at DESC);
        """)
        
        try:
            await self.db.execute(create_sql)
            await self.db.commit()
        except Exception as e:
            # Table might already exist with different schema
            await self.db.rollback()
            if "already exists" not in str(e):
                raise

    async def _insert_webhook(self, table_name: str, webhook: Webhook) -> None:
        """Insert webhook data into the destination table."""
        insert_sql = text(f"""
            INSERT INTO {table_name} (webhook_id, app_id, body, headers, source_ip)
            VALUES (:webhook_id, :app_id, :body, :headers, :source_ip)
        """)

        await self.db.execute(insert_sql, {
            "webhook_id": webhook.id,
            "app_id": webhook.app_id,
            "body": json.dumps(webhook.body),
            "headers": json.dumps(webhook.headers),
            "source_ip": webhook.source_ip,
        })
        await self.db.commit()


async def deliver_database(
    webhook: Webhook,
    destination: Destination,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Deliver a webhook to a database destination.
    
    Args:
        webhook: The webhook to deliver
        destination: The database destination configuration
        db: Database session
        
    Returns:
        Delivery result with table_name and rows_inserted
    """
    client = DatabaseDestination(db, destination)
    return await client.deliver(webhook)
