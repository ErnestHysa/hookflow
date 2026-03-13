"""Webhook templates for common event formats.

Provides pre-built templates for popular services like Stripe, GitHub, Shopify, etc.
"""

from typing import Any
from datetime import datetime
from enum import Enum


class TemplateProvider(str, Enum):
    """Template providers."""

    STRIPE = "stripe"
    GITHUB = "github"
    SHOPIFY = "shopify"
    PAYPAL = "paypal"
    SQUARE = "square"
    TWITCH = "twitch"
    DISCORD = "discord"
    SLACK = "slack"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    CUSTOM = "custom"


class WebhookTemplates:
    """Pre-built webhook templates for common event formats."""

    @staticmethod
    def get_template(provider: TemplateProvider, event_type: str) -> dict[str, Any]:
        """Get a template for a specific provider and event type.

        Args:
            provider: The service provider
            event_type: The event type (e.g., "payment_intent.succeeded")

        Returns:
            Template dict with sample payload and transformation rules
        """
        templates = {
            TemplateProvider.STRIPE: WebhookTemplates._stripe_templates(),
            TemplateProvider.GITHUB: WebhookTemplates._github_templates(),
            TemplateProvider.SHOPIFY: WebhookTemplates._shopify_templates(),
            TemplateProvider.PAYPAL: WebhookTemplates._paypal_templates(),
            TemplateProvider.SQUARE: WebhookTemplates._square_templates(),
            TemplateProvider.TWITCH: WebhookTemplates._twitch_templates(),
            TemplateProvider.DISCORD: WebhookTemplates._discord_templates(),
            TemplateProvider.SLACK: WebhookTemplates._slack_templates(),
            TemplateProvider.SENDGRID: WebhookTemplates._sendgrid_templates(),
            TemplateProvider.MAILGUN: WebhookTemplates._mailgun_templates(),
        }

        provider_templates = templates.get(provider, {})
        return provider_templates.get(event_type, {})

    @staticmethod
    def _stripe_templates() -> dict[str, dict[str, Any]]:
        """Stripe webhook templates."""
        return {
            "payment_intent.succeeded": {
                "name": "Stripe Payment Succeeded",
                "description": "Sent when a payment intent succeeds",
                "sample_payload": {
                    "id": "evt_1MqsPw2eZvKYlo2CzgYJyWT",
                    "object": "event",
                    "api_version": "2020-08-27",
                    "created": 1677656400,
                    "data": {
                        "object": {
                            "id": "pi_3MqsPw2eZvKYlo2C1wA7jPq",
                            "object": "payment_intent",
                            "amount": 2000,
                            "amount_capturable": 2000,
                            "created": 1677656400,
                            "currency": "usd",
                            "customer": "cus_NfffrDiWsSXwx",
                            "description": "Payment for order #12345",
                            "livemode": False,
                            "metadata": {
                                "order_id": "12345",
                            },
                            "status": "succeeded",
                        }
                    },
                    "livemode": False,
                    "pending_webhooks": 0,
                    "request": {
                        "id": "req_NfffrDiWsSXwx",
                        "idempotency_key": "pi_3MqsPw2eZvKYlo2C1wA7jPq",
                    },
                    "type": "payment_intent.succeeded",
                },
                "transformation_rules": {
                    "extract": {
                        "payment_id": "data.object.id",
                        "amount": "data.object.amount",
                        "currency": "data.object.currency",
                        "customer_id": "data.object.customer",
                        "description": "data.object.description",
                        "status": "data.object.status",
                        "metadata": "data.object.metadata",
                    },
                    "cast": {
                        "amount": "int",
                    },
                    "remove": ["livemode", "pending_webhooks"],
                },
            },
            "payment_intent.payment_failed": {
                "name": "Stripe Payment Failed",
                "description": "Sent when a payment intent fails",
                "sample_payload": {
                    "id": "evt_1MqsPw2eZvKYlo2CzgYJyWT",
                    "object": "event",
                    "api_version": "2020-08-27",
                    "created": 1677656400,
                    "data": {
                        "object": {
                            "id": "pi_3MqsPw2eZvKYlo2C1wA7jPq",
                            "object": "payment_intent",
                            "last_payment_error": {
                                "code": "card_declined",
                                "message": "Your card was declined.",
                            },
                            "amount": 2000,
                            "currency": "usd",
                            "status": "requires_payment_method",
                        }
                    },
                    "type": "payment_intent.payment_failed",
                },
                "transformation_rules": {
                    "extract": {
                        "payment_id": "data.object.id",
                        "amount": "data.object.amount",
                        "currency": "data.object.currency",
                        "error_code": "data.object.last_payment_error.code",
                        "error_message": "data.object.last_payment_error.message",
                    },
                },
            },
            "invoice.paid": {
                "name": "Stripe Invoice Paid",
                "description": "Sent when an invoice is paid",
                "sample_payload": {
                    "id": "evt_1MqsPw2eZvKYlo2CzgYJyWT",
                    "object": "event",
                    "data": {
                        "object": {
                            "id": "in_1MqsPw2eZvKYlo2C0tknN",
                            "object": "invoice",
                            "account_country": "US",
                            "amount_due": 2000,
                            "amount_paid": 2000,
                            "currency": "usd",
                            "customer": "cus_NfffrDiWsSXwx",
                            "status": "paid",
                        }
                    },
                    "type": "invoice.paid",
                },
                "transformation_rules": {
                    "extract": {
                        "invoice_id": "data.object.id",
                        "amount_paid": "data.object.amount_paid",
                        "currency": "data.object.currency",
                        "customer_id": "data.object.customer",
                    },
                },
            },
            "customer.created": {
                "name": "Stripe Customer Created",
                "description": "Sent when a new customer is created",
                "sample_payload": {
                    "id": "evt_1MqsPw2eZvKYlo2CzgYJyWT",
                    "object": "event",
                    "data": {
                        "object": {
                            "id": "cus_NfffrDiWsSXwx",
                            "object": "customer",
                            "name": "Jenny Rosen",
                            "email": "jennyrosen@example.com",
                            "created": 1677656400,
                        }
                    },
                    "type": "customer.created",
                },
                "transformation_rules": {
                    "extract": {
                        "customer_id": "data.object.id",
                        "name": "data.object.name",
                        "email": "data.object.email",
                    },
                },
            },
            "subscription.created": {
                "name": "Stripe Subscription Created",
                "description": "Sent when a subscription is created",
                "sample_payload": {
                    "id": "evt_1MqsPw2eZvKYlo2CzgYJyWT",
                    "object": "event",
                    "data": {
                        "object": {
                            "id": "sub_1MqsPw2eZvKYlo2C1xA1In",
                            "object": "subscription",
                            "customer": "cus_NfffrDiWsSXwx",
                            "status": "active",
                            "current_period_start": 1677656400,
                            "current_period_end": 1680334800,
                        }
                    },
                    "type": "subscription.created",
                },
                "transformation_rules": {
                    "extract": {
                        "subscription_id": "data.object.id",
                        "customer_id": "data.object.customer",
                        "status": "data.object.status",
                    },
                },
            },
        }

    @staticmethod
    def _github_templates() -> dict[str, dict[str, Any]]:
        """GitHub webhook templates."""
        return {
            "push": {
                "name": "GitHub Push",
                "description": "Sent when a push is made to a repository",
                "sample_payload": {
                    "ref": "refs/heads/main",
                    "repository": {
                        "id": 1296269,
                        "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                        "name": "Hello-World",
                        "full_name": "octocat/Hello-World",
                        "private": False,
                        "owner": {
                            "login": "octocat",
                            "id": 1,
                        },
                    },
                    "pusher": {
                        "name": "octocat",
                        "email": "octocat@github.com",
                    },
                    "sender": {
                        "login": "octocat",
                        "id": 1,
                    },
                    "commits": [
                        {
                            "id": "a11d14ef5ac4322ed3f6c7b44a9e3b",
                            "message": "Update README.md",
                            "timestamp": "2023-03-01T12:00:00Z",
                            "author": {
                                "name": "octocat",
                                "email": "octocat@github.com",
                            },
                        }
                    ],
                },
                "transformation_rules": {
                    "extract": {
                        "repo_name": "repository.name",
                        "repo_owner": "repository.owner.login",
                        "branch": "ref",
                        "pusher": "pusher.name",
                        "commit_count": "commits",
                        "latest_commit": "commits.0.id",
                    },
                    "events": ["push"],
                },
            },
            "pull_request": {
                "name": "GitHub Pull Request",
                "description": "Sent when a pull request is opened or modified",
                "sample_payload": {
                    "action": "opened",
                    "number": 1,
                    "pull_request": {
                        "id": 1,
                        "number": 1,
                        "state": "open",
                        "title": "Add new feature",
                        "user": {
                            "login": "octocat",
                        },
                        "body": "This PR adds a new feature",
                        "head": {
                            "ref": "new-feature",
                        },
                        "base": {
                            "ref": "main",
                        },
                    },
                    "repository": {
                        "id": 1296269,
                        "name": "Hello-World",
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "action": "action",
                        "pr_number": "number",
                        "title": "pull_request.title",
                        "state": "pull_request.state",
                        "author": "pull_request.user.login",
                        "head_branch": "pull_request.head.ref",
                        "base_branch": "pull_request.base.ref",
                    },
                    "events": ["pull_request"],
                },
            },
            "release": {
                "name": "GitHub Release",
                "description": "Sent when a release is published",
                "sample_payload": {
                    "action": "published",
                    "release": {
                        "id": 1,
                        "tag_name": "v1.0.0",
                        "name": "Version 1.0.0",
                        "body": "First release",
                        "author": {
                            "login": "octocat",
                        },
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "action": "action",
                        "tag": "release.tag_name",
                        "name": "release.name",
                        "author": "release.author.login",
                        "body": "release.body",
                    },
                },
            },
            "ping": {
                "name": "GitHub Ping",
                "description": "Sent when a webhook is configured",
                "sample_payload": {
                    "zen": "Keep it logically awesome.",
                    "hook_id": 1,
                },
                "transformation_rules": {
                    "extract": {
                        "hook_id": "hook_id",
                        "zen": "zen",
                    },
                },
            },
        }

    @staticmethod
    def _shopify_templates() -> dict[str, dict[str, Any]]:
        """Shopify webhook templates."""
        return {
            "orders/create": {
                "name": "Shopify Order Created",
                "description": "Sent when a new order is created",
                "sample_payload": {
                    "id": 1,
                    "email": "customer@example.com",
                    "created_at": "2023-03-01T12:00:00Z",
                    "updated_at": "2023-03-01T12:00:00Z",
                    "total_price": "100.00",
                    "currency": "USD",
                    "line_items": [
                        {
                            "id": 1,
                            "title": "Product Name",
                            "quantity": 1,
                            "price": "100.00",
                        }
                    ],
                },
                "transformation_rules": {
                    "extract": {
                        "order_id": "id",
                        "email": "email",
                        "total": "total_price",
                        "currency": "currency",
                        "item_count": "line_items",
                    },
                    "cast": {"total": "float"},
                },
            },
            "orders/updated": {
                "name": "Shopify Order Updated",
                "description": "Sent when an order is updated",
                "sample_payload": {
                    "id": 1,
                    "email": "customer@example.com",
                    "financial_status": "paid",
                    "fulfillment_status": None,
                },
                "transformation_rules": {
                    "extract": {
                        "order_id": "id",
                        "email": "email",
                        "financial_status": "financial_status",
                        "fulfillment_status": "fulfillment_status",
                    },
                },
            },
            "app/uninstalled": {
                "name": "Shopify App Uninstalled",
                "description": "Sent when an app is uninstalled",
                "sample_payload": {
                    "id": 1,
                    "name": "My App",
                },
                "transformation_rules": {
                    "extract": {
                        "app_id": "id",
                        "app_name": "name",
                    },
                },
            },
        }

    @staticmethod
    def _paypal_templates() -> dict[str, dict[str, Any]]:
        """PayPal webhook templates."""
        return {
            "PAYMENT.CAPTURE.COMPLETED": {
                "name": "PayPal Payment Captured",
                "description": "Sent when a payment is captured",
                "sample_payload": {
                    "id": "WH-1B23456789012345678",
                    "event_type": "PAYMENT.CAPTURE.COMPLETED",
                    "resource": {
                        "id": "1U2345678901234567",
                        "status": "COMPLETED",
                        "amount": "10.00",
                        "currency": "USD",
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "payment_id": "resource.id",
                        "amount": "resource.amount",
                        "currency": "resource.currency",
                        "status": "resource.status",
                    },
                },
            },
            "PAYMENT.SALE.REFUNDED": {
                "name": "PayPal Payment Refunded",
                "description": "Sent when a payment is refunded",
                "sample_payload": {
                    "id": "WH-1B23456789012345678",
                    "event_type": "PAYMENT.SALE.REFUNDED",
                    "resource": {
                        "id": "1U2345678901234567",
                        "state": "refunded",
                        "amount": {
                            "total": "-10.00",
                            "currency": "USD",
                        },
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "payment_id": "resource.id",
                        "refund_amount": "resource.amount.total",
                        "currency": "resource.amount.currency",
                    },
                },
            },
        }

    @staticmethod
    def _square_templates() -> dict[str, dict[str, Any]]:
        """Square webhook templates."""
        return {
            "payment.created": {
                "name": "Square Payment Created",
                "description": "Sent when a payment is created",
                "sample_payload": {
                    "merchant_id": "MY_MERCHANT_ID",
                    "location_id": "MY_LOCATION_ID",
                    "type": "payment.created",
                    "id": "JGHJ034",
                    "object": {
                        "payment": {
                            "id": "JGHJ034",
                            "amount_money": {
                                "amount": 1000,
                                "currency": "USD",
                            },
                            "status": "COMPLETED",
                        },
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "payment_id": "object.payment.id",
                        "amount": "object.payment.amount_money.amount",
                        "currency": "object.payment.amount_money.currency",
                        "status": "object.payment.status",
                    },
                    "cast": {"amount": "int"},
                },
            },
        }

    @staticmethod
    def _twitch_templates() -> dict[str, dict[str, Any]]:
        """Twitch webhook templates."""
        return {
            "stream.online": {
                "name": "Twitch Stream Online",
                "description": "Sent when a stream goes online",
                "sample_payload": {
                    "id": "1J2345678902345678",
                    "event_type": "stream.online",
                    "event_timestamp": "2023-03-01T12:00:00Z",
                    "version": "1.0",
                    "data": {
                        "id": "123456",
                        "broadcaster_id": "123456",
                        "broadcaster_name": "TestChannel",
                        "started_at": "2023-03-01T12:00:00Z",
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "stream_id": "data.id",
                        "channel": "data.broadcaster_name",
                        "started_at": "data.started_at",
                    },
                },
            },
        }

    @staticmethod
    def _discord_templates() -> dict[str, dict[str, Any]]:
        """Discord webhook templates."""
        return {
            "guild_member_add": {
                "name": "Discord Member Joined",
                "description": "Sent when a member joins a guild",
                "sample_payload": {
                    "id": "1J2345678902345678",
                    "guild_id": "1234567890",
                    "event": "GUILD_MEMBER_ADD",
                    "data": {
                        "user": {
                            "id": "123456789",
                            "username": "TestUser",
                            "discriminator": "1234",
                        },
                        "joined_at": "2023-03-01T12:00:00Z",
                    },
                },
                "transformation_rules": {
                    "extract": {
                        "user_id": "data.user.id",
                        "username": "data.user.username",
                        "joined_at": "data.joined_at",
                    },
                },
            },
        }

    @staticmethod
    def _slack_templates() -> dict[str, dict[str, Any]]:
        """Slack webhook templates."""
        return {
            "url_verification": {
                "name": "Slack URL Verification",
                "description": "Sent when verifying a webhook URL",
                "sample_payload": {
                    "token": "Jhj5dZrVaK7ZgHHdJLBMviq",
                    "challenge": "3eZbrw1aBm2rZhR8dZfOYHAkvwPFpRFxAi3v5D",
                    "type": "url_verification",
                },
                "transformation_rules": {
                    "extract": {
                        "challenge": "challenge",
                        "token": "token",
                    },
                },
            },
            "app_mention": {
                "name": "Slack App Mention",
                "description": "Sent when your app is mentioned",
                "sample_payload": {
                    "token": "Jhj5dZrVaK7ZgHHdJLBMviq",
                    "team_id": "T12345678",
                    "api_app_id": "A12345678",
                    "event": "app_mention",
                    "user": "U12345678",
                    "text": "<@U12345678> hello",
                },
                "transformation_rules": {
                    "extract": {
                        "user_id": "user",
                        "text": "text",
                    },
                },
            },
        }

    @staticmethod
    def _sendgrid_templates() -> dict[str, dict[str, Any]]:
        """SendGrid webhook templates."""
        return {
            "delivered": {
                "name": "SendGrid Email Delivered",
                "description": "Sent when an email is delivered",
                "sample_payload": [
                    {
                        "email": "recipient@example.com",
                        "event": "delivered",
                        "sg_message_id": "filter-1234567890.sendgrid-1",
                        "timestamp": 1677656400,
                    }
                ],
                "transformation_rules": {
                    "extract": {
                        "email": "0.email",
                        "sg_message_id": "0.sg_message_id",
                        "timestamp": "0.timestamp",
                    },
                },
            },
            "open": {
                "name": "SendGrid Email Opened",
                "description": "Sent when an email is opened",
                "sample_payload": [
                    {
                        "email": "recipient@example.com",
                        "event": "open",
                        "sg_message_id": "filter-1234567890.sendgrid-1",
                        "timestamp": 1677656400,
                    }
                ],
                "transformation_rules": {
                    "extract": {
                        "email": "0.email",
                        "sg_message_id": "0.sg_message_id",
                    },
                },
            },
            "click": {
                "name": "SendGrid Link Clicked",
                "description": "Sent when a link is clicked",
                "sample_payload": [
                    {
                        "email": "recipient@example.com",
                        "event": "click",
                        "url": "https://example.com",
                    }
                ],
                "transformation_rules": {
                    "extract": {
                        "email": "0.email",
                        "url": "0.url",
                    },
                },
            },
        }

    @staticmethod
    def _mailgun_templates() -> dict[str, dict[str, Any]]:
        """Mailgun webhook templates."""
        return {
            "delivered": {
                "name": "Mailgun Email Delivered",
                "description": "Sent when an email is delivered",
                "sample_payload": {
                    "signature": "a0b1c2d3e4f5",
                    "event-data": {
                        "timestamp": 1677656400,
                        "id": "1234567890",
                        "message": {
                            "headers": {
                                "message-id": "<1234567890@mailgun.example>",
                            },
                        },
                        "recipient": "recipient@example.com",
                    },
                    "event": "delivered",
                },
                "transformation_rules": {
                    "extract": {
                        "message_id": "event-data.message.headers.message-id",
                        "recipient": "event-data.recipient",
                        "timestamp": "event-data.timestamp",
                    },
                },
            },
        }

    @staticmethod
    def list_templates(provider: TemplateProvider | None = None) -> list[dict[str, Any]]:
        """List all available templates.

        Args:
            provider: Optional provider to filter by

        Returns:
            List of available templates
        """
        all_templates = []

        providers = [provider] if provider else list(TemplateProvider)

        for prov in providers:
            # Get the templates for each provider
            if prov == TemplateProvider.STRIPE:
                provider_templates = WebhookTemplates._stripe_templates()
            elif prov == TemplateProvider.GITHUB:
                provider_templates = WebhookTemplates._github_templates()
            elif prov == TemplateProvider.SHOPIFY:
                provider_templates = WebhookTemplates._shopify_templates()
            elif prov == TemplateProvider.PAYPAL:
                provider_templates = WebhookTemplates._paypal_templates()
            elif prov == TemplateProvider.SQUARE:
                provider_templates = WebhookTemplates._square_templates()
            elif prov == TemplateProvider.TWITCH:
                provider_templates = WebhookTemplates._twitch_templates()
            elif prov == TemplateProvider.DISCORD:
                provider_templates = WebhookTemplates._discord_templates()
            elif prov == TemplateProvider.SLACK:
                provider_templates = WebhookTemplates._slack_templates()
            elif prov == TemplateProvider.SENDGRID:
                provider_templates = WebhookTemplates._sendgrid_templates()
            elif prov == TemplateProvider.MAILGUN:
                provider_templates = WebhookTemplates._mailgun_templates()
            else:
                provider_templates = {}

            # List all event types in this provider's templates
            for event_type, template in provider_templates.items():
                if isinstance(template, dict) and "name" in template:
                    all_templates.append({
                        "provider": prov,
                        "event_type": event_type,
                        "name": template.get("name"),
                        "description": template.get("description"),
                    })

        return all_templates

    @staticmethod
    def create_sample_webhook(
        provider: TemplateProvider,
        event_type: str,
    ) -> dict[str, Any]:
        """Create a sample webhook for testing.

        Args:
            provider: The service provider
            event_type: The event type

        Returns:
            Sample webhook payload
        """
        template = WebhookTemplates.get_template(provider, event_type)
        return template.get("sample_payload", {})

    @staticmethod
    def get_transformation_rules(
        provider: TemplateProvider,
        event_type: str,
    ) -> dict[str, Any] | None:
        """Get transformation rules for a template.

        Args:
            provider: The service provider
            event_type: The event type

        Returns:
            Transformation rules dict or None
        """
        template = WebhookTemplates.get_template(provider, event_type)
        return template.get("transformation_rules")
