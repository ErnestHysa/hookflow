"""HookFlow CLI - Command-line tool for testing webhooks."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import typer

from hookflow.core.config import settings
from hookflow.services.templates import TemplateProvider, WebhookTemplates

app = typer.Typer(
    name="hookflow",
    help="HookFlow CLI - Test webhooks and manage your integration",
    no_args_is_help=True,
    add_completion=False,
)

# Default API URL
API_URL = "http://localhost:8000/api/v1"


def get_client() -> httpx.AsyncClient:
    """Get an HTTP client with default configuration."""
    return httpx.AsyncClient(
        base_url=API_URL,
        timeout=30.0,
        headers={"Content-Type": "application/json"},
    )


@app.command()
def send(
    url: str = typer.Argument(..., help="Webhook URL (e.g., /api/v1/webhook/{app_id})"),
    data: str = typer.Option(None, "--data", "-d", help="JSON payload to send"),
    data_file: str = typer.Option(None, "--file", "-f", help="Read JSON payload from file"),
    method: str = typer.Option("POST", "--method", "-X", help="HTTP method"),
    headers: str = typer.Option(None, "--header", "-H", help="Add header (can be used multiple times)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full response"),
):
    """Send a test webhook to an endpoint."""
    asyncio.run(_send_webhook(url, data, data_file, method, headers, verbose))


@app.command()
def test(
    app_id: str = typer.Argument(..., help="App ID to send webhook to"),
    template: str = typer.Option(None, "--template", "-t", help="Use a template (stripe, github, etc.)"),
    event: str = typer.Option(None, "--event", "-e", help="Event type for template"),
    payload: str = typer.Option(None, "--payload", "-p", help="JSON payload"),
    payload_file: str = typer.Option(None, "--file", "-f", help="Read payload from file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full response"),
):
    """Send a test webhook to your app."""
    asyncio.run(_test_webhook(app_id, template, event, payload, payload_file, verbose))


@app.command()
def replay(
    webhook_id: str = typer.Argument(..., help="Webhook ID to replay"),
    destination_id: str = typer.Option(None, "--destination", "-d", help="Specific destination ID"),
):
    """Replay a webhook to one or all destinations."""
    asyncio.run(_replay_webhook(webhook_id, destination_id))


@app.command()
def list_dlq(
    app_id: str = typer.Argument(..., help="App ID to list failed deliveries for"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items to show"),
):
    """List failed webhook deliveries (Dead Letter Queue)."""
    asyncio_run(_list_dlq(app_id, limit))


@app.command()
def dlq_stats(
    app_id: str = typer.Argument(..., help="App ID to get stats for"),
):
    """Show Dead Letter Queue statistics."""
    asyncio.run(_dlq_stats(app_id))


@app.command()
def templates(
    provider: str = typer.Option(None, "--provider", "-p", help="Filter by provider"),
):
    """List available webhook templates."""
    asyncio_run(_list_templates(provider))


@app.command()
def template(
    provider: str = typer.Argument(..., help="Template provider (stripe, github, etc.)"),
    event: str = typer.Argument(..., help="Event type"),
):
    """Show details for a specific template."""
    _show_template(provider, event)


# Implementation functions

async def _send_webhook(
    url: str,
    data: str | None,
    data_file: str | None,
    method: str,
    headers: str | None,
    verbose: bool,
):
    """Send a webhook to an endpoint."""
    async with get_client() as client:
        # Parse headers
        http_headers = {}
        if headers:
            for h in headers.split(","):
                if ":" in h:
                    key, value = h.split(":", 1)
                    http_headers[key.strip()] = value.strip()

        # Get payload
        body: dict[str, Any] | None = None
        if data:
            body = json.loads(data)
        elif data_file:
            with open(data_file) as f:
                body = json.load(f)

        if not body:
            body = {"test": True, "timestamp": datetime.now().isoformat()}

        # Send request
        typer.echo(f"Sending {method} request to: {url}")
        if verbose:
            typer.echo(f"Payload: {json.dumps(body, indent=2)}")

        response = await client.request(method, url, json=body, headers=http_headers)

        # Show response
        typer.echo(f"\nStatus: {response.status_code}")
        if verbose:
            typer.echo(f"Headers: {dict(response.headers)}")
            typer.echo(f"\nBody:\n{response.text}")


async def _test_webhook(
    app_id: str,
    template: str | None,
    event: str | None,
    payload: str | None,
    payload_file: str | None,
    verbose: bool,
):
    """Send a test webhook to an app."""
    async with get_client() as client:
        url = f"/webhook/{app_id}"
        body: dict[str, Any] | None = None

        # Use template if specified
        if template and event:
            try:
                provider = TemplateProvider(template.lower())
                body = WebhookTemplates.create_sample_webhook(provider, event)
                typer.echo(f"Using template: {template}/{event}")
            except ValueError:
                typer.error(f"Unknown provider: {template}")
                raise typer.Exit(1)
        elif payload:
            body = json.loads(payload)
        elif payload_file:
            with open(payload_file) as f:
                body = json.load(f)
        else:
            body = {"test": True, "timestamp": datetime.now().isoformat()}

        if verbose:
            typer.echo(f"Sending to: {url}")
            typer.echo(f"Payload: {json.dumps(body, indent=2)}")

        response = await client.post(url, json=body)

        typer.echo(f"\nStatus: {response.status_code}")
        if verbose:
            typer.echo(f"Headers: {dict(response.headers)}")
        typer.echo(f"\nBody:\n{response.text}")

        # Show rate limit info if present
        if "x-ratelimit-remaining" in response.headers:
            typer.echo(f"\nRate Limit:")
            typer.echo(f"  Remaining: {response.headers['x-ratelimit-remaining']}")
            typer.echo(f"  Limit: {response.headers['x-ratelimit-limit']}")


async def _replay_webhook(webhook_id: str, destination_id: str | None):
    """Replay a webhook."""
    async with get_client() as client:
        url = f"/webhooks/{webhook_id}/replay"

        body: dict[str, Any] = {}
        if destination_id:
            body["destination_ids"] = [destination_id]

        typer.echo(f"Replaying webhook: {webhook_id}")
        response = await client.post(url, json=body)

        typer.echo(f"\nStatus: {response.status_code}")
        typer.echo(f"Response:\n{response.text}")


async def _list_dlq(app_id: str, limit: int):
    """List failed webhook deliveries."""
    async with get_client() as client:
        url = f"/apps/{app_id}/dlq?limit={limit}"
        response = await client.get(url)

        if response.status_code != 200:
            typer.error(f"Error: {response.status_code}")
            typer.echo(response.text)
            raise typer.Exit(1)

        data = response.json()

        typer.echo(f"Dead Letter Queue for app: {app_id}")
        typer.echo(f"Total failed: {data['total']}\n")

        if data["items"]:
            for item in data["items"]:
                typer.echo(f"  [{item['status']}] {item['destination_name']}")
                typer.echo(f"    ID: {item['id']}")
                typer.echo(f"    Error: {item.get('error_message', 'N/A')}")
                typer.echo(f"    Created: {item['created_at']}")
                typer.echo()
        else:
            typer.echo("No failed deliveries found.")


async def _dlq_stats(app_id: str):
    """Show DLQ statistics."""
    async with get_client() as client:
        url = f"/apps/{app_id}/dlq/stats"
        response = await client.get(url)

        if response.status_code != 200:
            typer.error(f"Error: {response.status_code}")
            typer.echo(response.text)
            raise typer.Exit(1)

        stats = response.json()

        typer.echo(f"Dead Letter Queue Statistics for app: {app_id}\n")
        typer.echo(f"Total Failed: {stats['total_failed']}")
        typer.echo(f"\nBy Status:")
        for status, count in stats.get("by_status", {}).items():
            typer.echo(f"  {status}: {count}")

        if stats.get("top_errors"):
            typer.echo(f"\nTop Errors:")
            for err in stats["top_errors"][:5]:
                typer.echo(f"  [{err['count']}] {err['error'][:60]}")


async def _list_templates(provider: str | None):
    """List available templates."""
    if provider:
        try:
            provider_enum = TemplateProvider(provider.lower())
            templates = WebhookTemplates.list_templates(provider_enum)
        except ValueError:
            typer.error(f"Unknown provider: {provider}")
            raise typer.Exit(1)
    else:
        templates = WebhookTemplates.list_templates()

    typer.echo("Available Webhook Templates\n")

    if provider:
        typer.echo(f"Provider: {provider}\n")
    else:
        typer.echo("All Providers\n")

    # Group by provider
    from collections import defaultdict
    grouped = defaultdict(list)
    for t in templates:
        grouped[t["provider"]].append(t)

    for prov_name, prov_templates in grouped.items():
        typer.echo(f"  {prov_name}:")
        for t in prov_templates:
            typer.echo(f"    {t['event_type']}: {t['name']}")
        typer.echo()


def _show_template(provider: str, event: str):
    """Show template details."""
    try:
        provider_enum = TemplateProvider(provider.lower())
    except ValueError:
        typer.error(f"Unknown provider: {provider}")
        raise typer.Exit(1)

    template = WebhookTemplates.get_template(provider_enum, event)

    if not template or "name" not in template:
        typer.error(f"Template not found: {provider}/{event}")
        raise typer.Exit(1)

    typer.echo(f"Template: {provider}/{event}")
    typer.echo(f"Name: {template['name']}")
    typer.echo(f"Description: {template['description']}\n")

    if "sample_payload" in template:
        typer.echo("Sample Payload:")
        typer.echo(json.dumps(template["sample_payload"], indent=2))
        typer.echo()

    if "transformation_rules" in template:
        typer.echo("Transformation Rules:")
        typer.echo(json.dumps(template["transformation_rules"], indent=2))


def main():
    """Run the CLI."""
    # Set API URL from env if available
    global API_URL
    import os
    api_url = os.getenv("HOOKFLOW_API_URL")
    if api_url:
        API_URL = api_url

    app()


if __name__ == "__main__":
    main()
