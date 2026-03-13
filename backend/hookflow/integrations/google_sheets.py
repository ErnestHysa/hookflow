"""Google Sheets destination integration - appends rows to Google Sheets."""

import os
from datetime import datetime
from typing import Any

from hookflow.models.app import Webhook, Destination


class GoogleSheetsDestination:
    """Delivers webhooks to Google Sheets."""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, destination: Destination):
        self.destination = destination
        self.config = destination.config or {}
        self.spreadsheet_id = self.config.get("spreadsheet_id")
        self.sheet_name = self.config.get("sheet_name", "Sheet1")
        self.field_mappings = self.config.get("field_mappings", {})

    async def deliver(self, webhook: Webhook) -> dict[str, Any]:
        """
        Deliver webhook payload to a Google Sheets.
        
        Appends a row with mapped values to the configured sheet.
        """
        if not self.spreadsheet_id:
            raise ValueError("Google Sheets spreadsheet ID not configured")

        # Build row values from webhook data
        row_data = await self._build_row(webhook)

        # Append row via Google Sheets API
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            raise ValueError(
                "Google packages not installed. Run: pip install google-api-python-client google-auth"
            )

        # Load service account credentials
        credentials_path = os.environ.get("GOOGLE_CLOUD_CREDENTIALS_PATH")
        if not credentials_path:
            raise ValueError(
                "GOOGLE_CLOUD_CREDENTIALS_PATH environment variable not set"
            )

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=self.SCOPES,
        )

        # Build the Sheets API service
        service = build("sheets", "v4", credentials=credentials)

        # Append row
        body = {"values": [row_data]}
        
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

        updates = result.get("updates", {})
        return {
            "provider": "google_sheets",
            "spreadsheet_id": self.spreadsheet_id,
            "sheet_name": self.sheet_name,
            "rows_updated": updates.get("updatedRows", 0),
        }

    async def _build_row(self, webhook: Webhook) -> list[Any]:
        """
        Build a row of values from webhook data using field mappings.
        
        Field mappings map JSON paths to column letters (A, B, C, etc.).
        We need to sort by column letter and return values in order.
        """
        # Build mapping of column index to value
        col_values = {}
        
        for json_path, column_letter in self.field_mappings.items():
            value = self._extract_value(webhook, json_path)
            
            # Convert column letter to index (A=0, B=1, etc.)
            col_index = self._column_letter_to_index(column_letter)
            col_values[col_index] = self._format_value(value)

        # Build row with values in correct column order
        max_col = max(col_values.keys()) if col_values else 0
        row = [col_values.get(i, "") for i in range(max_col + 1)]
        
        return row

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

    def _column_letter_to_index(self, column: str) -> int:
        """Convert column letter to zero-based index (A=0, B=1, AA=26, etc.)."""
        result = 0
        for char in column.upper():
            if not char.isalpha():
                continue
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result - 1

    def _format_value(self, value: Any) -> str:
        """Format a value for Google Sheets cell."""
        if value is None:
            return ""
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, dict):
            # For JSON objects, stringify
            import json
            return json.dumps(value)
        elif isinstance(value, list):
            # For arrays, stringify
            import json
            return json.dumps(value)
        else:
            return str(value)


async def deliver_google_sheets(
    webhook: Webhook,
    destination: Destination,
) -> dict[str, Any]:
    """
    Deliver a webhook to a Google Sheets.
    
    Args:
        webhook: The webhook to deliver
        destination: The Google Sheets destination configuration
        
    Returns:
        Delivery result with spreadsheet info and rows updated
    """
    client = GoogleSheetsDestination(destination)
    return await client.deliver(webhook)
