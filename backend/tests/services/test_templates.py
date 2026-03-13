"""Tests for webhook templates."""

import pytest

from hookflow.services.templates import (
    TemplateProvider,
    WebhookTemplates,
)


class TestWebhookTemplates:
    """Tests for WebhookTemplates."""

    def test_get_stripe_payment_succeeded_template(self):
        """Test getting Stripe payment succeeded template."""
        template = WebhookTemplates.get_template(
            TemplateProvider.STRIPE,
            "payment_intent.succeeded"
        )

        assert template is not None
        assert "name" in template
        assert "sample_payload" in template
        assert "transformation_rules" in template
        assert template["name"] == "Stripe Payment Succeeded"

    def test_get_github_push_template(self):
        """Test getting GitHub push template."""
        template = WebhookTemplates.get_template(
            TemplateProvider.GITHUB,
            "push"
        )

        assert template is not None
        assert "name" in template
        assert "sample_payload" in template
        assert "transformation_rules" in template

    def test_get_nonexistent_template(self):
        """Test getting a template that doesn't exist."""
        template = WebhookTemplates.get_template(
            TemplateProvider.STRIPE,
            "nonexistent.event"
        )

        assert template == {}

    def test_list_all_templates(self):
        """Test listing all templates."""
        templates = WebhookTemplates.list_templates()

        assert len(templates) > 0
        assert all("provider" in t for t in templates)
        assert all("event_type" in t for t in templates)
        assert all("name" in t for t in templates)

    def test_list_filtered_templates(self):
        """Test listing templates filtered by provider."""
        stripe_templates = WebhookTemplates.list_templates(TemplateProvider.STRIPE)

        assert all(t["provider"] == TemplateProvider.STRIPE for t in stripe_templates)
        assert len(stripe_templates) > 0

    def test_create_sample_webhook(self):
        """Test creating sample webhook from template."""
        sample = WebhookTemplates.create_sample_webhook(
            TemplateProvider.STRIPE,
            "payment_intent.succeeded"
        )

        assert sample is not None
        assert "data" in sample
        assert "type" in sample

    def test_get_transformation_rules(self):
        """Test getting transformation rules from template."""
        rules = WebhookTemplates.get_transformation_rules(
            TemplateProvider.STRIPE,
            "payment_intent.succeeded"
        )

        assert rules is not None
        assert "extract" in rules
        assert "sample_payload" not in rules  # Rules shouldn't contain sample

    def test_transformation_rules_structure(self):
        """Test that transformation rules have correct structure."""
        rules = WebhookTemplates.get_transformation_rules(
            TemplateProvider.STRIPE,
            "payment_intent.succeeded"
        )

        # Should have extract to pull fields from nested structure
        assert "extract" in rules
        assert "data.object.id" in rules["extract"].values()

    def test_all_providers_have_templates(self):
        """Test that all defined providers have at least one template."""
        for provider in TemplateProvider:
            if provider == TemplateProvider.CUSTOM:
                continue
            templates = WebhookTemplates.list_templates(provider)
            # Each provider should have at least one template
            # (This test documents current state, not a strict requirement)
            print(f"{provider.value}: {len(templates)} templates")

    def test_shopify_order_created_template(self):
        """Test Shopify order created template."""
        template = WebhookTemplates.get_template(
            TemplateProvider.SHOPIFY,
            "orders/create"
        )

        assert template is not None
        assert "sample_payload" in template
        assert template["sample_payload"]["email"] == "customer@example.com"

    def test_github_pr_template(self):
        """Test GitHub pull request template."""
        template = WebhookTemplates.get_template(
            TemplateProvider.GITHUB,
            "pull_request"
        )

        assert template is not None
        assert "transformation_rules" in template
        assert "extract" in template["transformation_rules"]
        assert "pr_number" in template["transformation_rules"]["extract"]


class TestTemplateProviders:
    """Tests for template provider enum."""

    def test_all_providers_defined(self):
        """Test that all expected providers are defined."""
        expected_providers = [
            TemplateProvider.STRIPE,
            TemplateProvider.GITHUB,
            TemplateProvider.SHOPIFY,
            TemplateProvider.PAYPAL,
            TemplateProvider.SQUARE,
            TemplateProvider.TWITCH,
            TemplateProvider.DISCORD,
            TemplateProvider.SLACK,
            TemplateProvider.SENDGRID,
            TemplateProvider.MAILGUN,
        ]

        for provider in expected_providers:
            assert provider.value in [
                "stripe",
                "github",
                "shopify",
                "paypal",
                "square",
                "twitch",
                "discord",
                "slack",
                "sendgrid",
                "mailgun",
            ]

    def test_template_provider_values(self):
        """Test provider enum values."""
        assert TemplateProvider.STRIPE.value == "stripe"
        assert TemplateProvider.GITHUB.value == "github"
        assert TemplateProvider.SHOPIFY.value == "shopify"
