"""Integration modules for delivering webhooks to various destinations."""

from hookflow.integrations.database import DatabaseDestination, deliver_database
from hookflow.integrations.email import EmailDestination, deliver_email
from hookflow.integrations.notion import NotionDestination, deliver_notion
from hookflow.integrations.airtable import AirtableDestination, deliver_airtable
from hookflow.integrations.google_sheets import (
    GoogleSheetsDestination,
    deliver_google_sheets,
)

__all__ = [
    "DatabaseDestination",
    "deliver_database",
    "EmailDestination",
    "deliver_email",
    "NotionDestination",
    "deliver_notion",
    "AirtableDestination",
    "deliver_airtable",
    "GoogleSheetsDestination",
    "deliver_google_sheets",
]

# Integration type mapping
INTEGRATION_TYPES = {
    "database": ("DatabaseDestination", "deliver_database"),
    "email": ("EmailDestination", "deliver_email"),
    "notion": ("NotionDestination", "deliver_notion"),
    "airtable": ("AirtableDestination", "deliver_airtable"),
    "google_sheets": ("GoogleSheetsDestination", "deliver_google_sheets"),
}
