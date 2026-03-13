"""Notion destination integration - creates pages in Notion databases."""

from typing import Any
from urllib.parse import urlparse

from hookflow.models.app import Webhook, Destination


class NotionDestination:
    """Delivers webhooks to Notion databases."""

    NOTION_API_BASE = "https://api.notion.com/v1"

    def __init__(self, destination: Destination):
        self.destination = destination
        self.config = destination.config or {}
        self.api_key = self.config.get("api_key")
        self.database_id = self.config.get("database_id")
        self.field_mappings = self.config.get("field_mappings", {})

    async def deliver(self, webhook: Webhook, http_client) -> dict[str, Any]:
        """
        Deliver webhook payload to a Notion database.
        
        Creates a new page in the configured database with mapped properties.
        """
        if not self.api_key:
            raise ValueError("Notion API key not configured")
        if not self.database_id:
            raise ValueError("Notion database ID not configured")

        # Build page properties from webhook data
        properties = await self._build_properties(webhook)

        # Create page via Notion API
        page_data = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        response = await http_client.post(
            f"{self.NOTION_API_BASE}/pages",
            json=page_data,
            headers=headers,
        )

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            raise RuntimeError(f"Notion API error: {error_data}")

        result = response.json()
        return {
            "provider": "notion",
            "page_id": result.get("id"),
            "url": result.get("url"),
        }

    async def _build_properties(self, webhook: Webhook) -> dict[str, Any]:
        """Build Notion page properties from webhook data using field mappings."""
        properties = {}
        
        for json_path, mapping in self.field_mappings.items():
            value = self._extract_value(webhook, json_path)
            property_id = mapping.get("property_id")
            prop_type = mapping.get("type", "rich_text")

            if not property_id:
                continue

            if value is None:
                continue

            properties[property_id] = self._format_property(value, prop_type)

        return properties

    def _extract_value(self, webhook: Webhook, json_path: str) -> Any:
        """Extract value from webhook body using dot notation path."""
        # Handle "webhook.field" paths
        parts = json_path.split(".")
        
        # Start with webhook body
        obj = webhook.body or {}
        
        # Traverse path
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif isinstance(obj, list) and part.isdigit():
                idx = int(part)
                obj = obj[idx] if idx < len(obj) else None
            else:
                return None
        
        return obj

    def _format_property(self, value: Any, prop_type: str) -> dict[str, Any]:
        """Format a value according to Notion property type."""
        if prop_type == "title":
            return {"title": [{"text": {"content": str(value)}}]}
        
        elif prop_type == "rich_text":
            return {"rich_text": [{"text": {"content": str(value)}}]}
        
        elif prop_type == "number":
            return {"number": float(value) if isinstance(value, (int, float)) else 0}
        
        elif prop_type == "select":
            return {"select": {"name": str(value)}}
        
        elif prop_type == "date":
            # Format as ISO 8601 date string
            if isinstance(value, str):
                date_str = value
            else:
                from datetime import datetime
                if hasattr(value, "isoformat"):
                    date_str = value.isoformat()
                else:
                    date_str = str(value)
            return {"date": {"start": date_str}}
        
        elif prop_type == "checkbox":
            return {"checkbox": bool(value)}
        
        elif prop_type == "email":
            return {"email": str(value)}
        
        elif prop_type == "url":
            return {"url": str(value)}
        
        else:
            # Default to rich_text
            return {"rich_text": [{"text": {"content": str(value)}}]}


async def deliver_notion(
    webhook: Webhook,
    destination: Destination,
    http_client,
) -> dict[str, Any]:
    """
    Deliver a webhook to a Notion database.
    
    Args:
        webhook: The webhook to deliver
        destination: The Notion destination configuration
        http_client: HTTP client for making API requests
        
    Returns:
        Delivery result with Notion page ID and URL
    """
    client = NotionDestination(destination)
    return await client.deliver(webhook, http_client)
