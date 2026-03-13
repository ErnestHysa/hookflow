"""Airtable destination integration - creates records in Airtable tables."""

from typing import Any

from hookflow.models.app import Webhook, Destination


class AirtableDestination:
    """Delivers webhooks to Airtable tables."""

    AIRTABLE_API_BASE = "https://api.airtable.com/v0"

    def __init__(self, destination: Destination):
        self.destination = destination
        self.config = destination.config or {}
        self.access_token = self.config.get("access_token")
        self.base_id = self.config.get("base_id")
        self.table_id = self.config.get("table_id")
        self.field_mappings = self.config.get("field_mappings", {})

    async def deliver(self, webhook: Webhook, http_client) -> dict[str, Any]:
        """
        Deliver webhook payload to an Airtable table.
        
        Creates a new record with fields mapped from webhook data.
        """
        if not self.access_token:
            raise ValueError("Airtable access token not configured")
        if not self.base_id:
            raise ValueError("Airtable base ID not configured")
        if not self.table_id:
            raise ValueError("Airtable table ID not configured")

        # Build record fields from webhook data
        fields = await self._build_fields(webhook)

        # Create record via Airtable API
        record_data = {
            "records": [
                {
                    "fields": fields,
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        response = await http_client.post(
            f"{self.AIRTABLE_API_BASE}/{self.base_id}/{self.table_id}",
            json=record_data,
            headers=headers,
        )

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("error", {}).get("message", "Unknown error")
            raise RuntimeError(f"Airtable API error: {error_msg}")

        result = response.json()
        records = result.get("records", [])
        
        if records:
            return {
                "provider": "airtable",
                "record_id": records[0].get("id"),
                "created_time": records[0].get("createdTime"),
            }
        
        return {"provider": "airtable", "status": "unknown"}

    async def _build_fields(self, webhook: Webhook) -> dict[str, Any]:
        """Build Airtable record fields from webhook data using field mappings."""
        fields = {}
        
        for json_path, field_name in self.field_mappings.items():
            value = self._extract_value(webhook, json_path)
            
            if value is not None:
                # Convert value to Airtable-compatible format
                fields[field_name] = self._format_value(value)

        return fields

    def _extract_value(self, webhook: Webhook, json_path: str) -> Any:
        """Extract value from webhook body using dot notation path."""
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

    def _format_value(self, value: Any) -> Any:
        """Format a value for Airtable."""
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, list):
            # Airtable arrays for multiple select or attachment
            if len(value) > 0 and isinstance(value[0], dict):
                # Assume attachment format
                return value
            return value
        elif isinstance(value, dict):
            # For single select, extract name if present
            if "name" in value:
                return value["name"]
            # Otherwise stringify
            return str(value)
        else:
            return str(value) if value is not None else None


async def deliver_airtable(
    webhook: Webhook,
    destination: Destination,
    http_client,
) -> dict[str, Any]:
    """
    Deliver a webhook to an Airtable table.
    
    Args:
        webhook: The webhook to deliver
        destination: The Airtable destination configuration
        http_client: HTTP client for making API requests
        
    Returns:
        Delivery result with Airtable record ID
    """
    client = AirtableDestination(destination)
    return await client.deliver(webhook, http_client)
