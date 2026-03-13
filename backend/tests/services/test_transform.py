"""Tests for webhook transformation rules."""

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import App, User, Destination, Webhook
from hookflow.services.webhook import WebhookService


@pytest_asyncio.fixture
async def test_webhook_service(db_session: AsyncSession) -> WebhookService:
    """Create a webhook service for testing."""
    return WebhookService(db_session)


class TestWebhookTransformations:
    """Tests for webhook transformation rules."""

    def test_extract_fields(self, test_webhook_service: WebhookService):
        """Test extracting specific fields from webhook body."""
        body = {
            "user": {"id": 123, "name": "Alice"},
            "event": "user.created",
            "timestamp": "2024-01-01T00:00:00Z",
        }

        rules = {
            "extract": {
                "user_id": "user.id",
                "user_name": "user.name",
                "event_type": "event",
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result == {
            "user_id": 123,
            "user_name": "Alice",
            "event_type": "user.created",
        }

    def test_filter_keys(self, test_webhook_service: WebhookService):
        """Test filtering to keep only specified keys."""
        body = {
            "id": 123,
            "name": "Alice",
            "email": "alice@example.com",
            "password": "secret",
        }

        rules = {
            "filter": ["id", "name"]
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result == {"id": 123, "name": "Alice"}
        assert "email" not in result
        assert "password" not in result

    def test_remove_fields(self, test_webhook_service: WebhookService):
        """Test removing specific fields."""
        body = {
            "id": 123,
            "name": "Alice",
            "email": "alice@example.com",
            "internal_notes": "Confidential",
        }

        rules = {
            "remove": ["internal_notes"]
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result == {
            "id": 123,
            "name": "Alice",
            "email": "alice@example.com",
        }

    def test_rename_fields(self, test_webhook_service: WebhookService):
        """Test renaming fields."""
        body = {
            "user_id": 123,
            "user_name": "Alice",
        }

        rules = {
            "rename": {
                "user_id": "id",
                "user_name": "name"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result == {"id": 123, "name": "Alice"}

    def test_flatten_dict(self, test_webhook_service: WebhookService):
        """Test flattening nested structures."""
        body = {
            "user": {
                "id": 123,
                "profile": {
                    "name": "Alice",
                    "age": 30
                }
            }
        }

        rules = {
            "flatten": True
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert "user.id" in result
        assert "user.profile.name" in result
        assert result["user.id"] == 123
        assert result["user.profile.name"] == "Alice"

    def test_add_static_fields(self, test_webhook_service: WebhookService):
        """Test adding static fields."""
        body = {
            "id": 123,
            "name": "Alice",
        }

        rules = {
            "add": {
                "source": "webhook",
                "version": "1.0"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result == {
            "id": 123,
            "name": "Alice",
            "source": "webhook",
            "version": "1.0"
        }

    def test_map_values(self, test_webhook_service: WebhookService):
        """Test mapping field values."""
        body = {
            "status": "pending",
            "priority": "high"
        }

        rules = {
            "map": {
                "status": {"pending": "P", "active": "A"},
                "priority": {"high": 1, "medium": 2, "low": 3}
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result["status"] == "P"
        assert result["priority"] == 1

    def test_cast_values(self, test_webhook_service: WebhookService):
        """Test type casting."""
        body = {
            "count": "42",
            "price": "19.99",
            "active": "true",
            "data": '{"key": "value"}'
        }

        rules = {
            "cast": {
                "count": "int",
                "price": "float",
                "active": "bool",
                "data": "json"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result["count"] == 42
        assert isinstance(result["count"], int)
        assert result["price"] == 19.99
        assert isinstance(result["price"], float)
        assert result["active"] is True
        assert isinstance(result["active"], bool)
        assert result["data"] == {"key": "value"}

    def test_filter_values_equality(self, test_webhook_service: WebhookService):
        """Test filtering based on field value equality."""
        body = {
            "event": "user.created",
            "user": {"role": "admin"},
        }

        rules = {
            "filter_values": {
                "event": "user.created"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)
        # Should pass filter and return the body
        assert result["event"] == "user.created"

        # Now test a non-matching filter
        rules["filter_values"]["event"] = "user.deleted"
        result = test_webhook_service._apply_transform(body, rules)
        # Should not match and return empty dict
        assert result == {}

    def test_filter_values_operators(self, test_webhook_service: WebhookService):
        """Test filtering with comparison operators."""
        body = {
            "amount": 150,
            "status": "active",
        }

        # Test $gt
        rules = {"filter_values": {"amount": {"$gt": 100}}}
        result = test_webhook_service._apply_transform(body, rules)
        assert result["amount"] == 150  # Should match

        # Test $lt
        rules = {"filter_values": {"amount": {"$lt": 200}}}
        result = test_webhook_service._apply_transform(body, rules)
        assert result["amount"] == 150  # Should match

        # Test $ne
        rules = {"filter_values": {"status": {"$ne": "inactive"}}}
        result = test_webhook_service._apply_transform(body, rules)
        assert result["status"] == "active"  # Should match

        # Test $in
        rules = {"filter_values": {"status": {"$in": ["active", "pending"]}}}
        result = test_webhook_service._apply_transform(body, rules)
        assert result["status"] == "active"  # Should match

        # Test $nin
        rules = {"filter_values": {"status": {"$nin": ["inactive", "deleted"]}}}
        result = test_webhook_service._apply_transform(body, rules)
        assert result["status"] == "active"  # Should match

    def test_filter_values_contains(self, test_webhook_service: WebhookService):
        """Test $contains operator for string matching."""
        body = {
            "message": "Error: Connection failed",
            "code": "ERR_001"
        }

        rules = {
            "filter_values": {
                "message": {"$contains": "Error"}
            }
        }

        result = test_webhook_service._apply_transform(body, rules)
        assert result["message"] == "Error: Connection failed"

        # Test non-matching
        rules["filter_values"]["message"] = {"$contains": "Success"}
        result = test_webhook_service._apply_transform(body, rules)
        assert result == {}

    def test_event_type_filtering(self, test_webhook_service: WebhookService):
        """Test filtering by event type."""
        body = {
            "event": "user.created",
            "data": {"name": "Alice"}
        }

        # Matching event
        rules = {
            "events": ["user.created", "user.updated"]
        }

        result = test_webhook_service._apply_transform(body, rules)
        assert result["event"] == "user.created"

        # Non-matching event
        rules["events"] = ["order.created", "payment.completed"]
        result = test_webhook_service._apply_transform(body, rules)
        assert result == {}  # Should be filtered out

    def test_complex_transformation(self, test_webhook_service: WebhookService):
        """Test a complex transformation with multiple rules."""
        body = {
            "event": "order.created",
            "data": {
                "order": {
                    "id": "ORD-123",
                    "total": 99.99,
                    "customer": {
                        "email": "customer@example.com"
                    }
                }
            }
        }

        rules = {
            "filter_values": {"event": "order.created"},
            "extract": {
                "order_id": "data.order.id",
                "amount": "data.order.total",
                "customer_email": "data.order.customer.email"
            },
            "cast": {"amount": "float"},
            "add": {"currency": "USD"},
            "remove": ["event"]
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result == {
            "order_id": "ORD-123",
            "amount": 99.99,
            "customer_email": "customer@example.com",
            "currency": "USD"
        }

    def test_nested_array_access(self, test_webhook_service: WebhookService):
        """Test accessing array elements."""
        body = {
            "items": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"}
            ]
        }

        rules = {
            "extract": {
                "first_item_id": "items.0.id",
                "first_item_name": "items.0.name"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result["first_item_id"] == 1
        assert result["first_item_name"] == "Item 1"

    def test_wildcard_access(self, test_webhook_service: WebhookService):
        """Test wildcard access for arrays."""
        body = {
            "users": [
                {"name": "Alice", "role": "admin"},
                {"name": "Bob", "role": "user"}
            ]
        }

        rules = {
            "extract": {
                "first_user_name": "users.*.name"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        # Wildcard with subsequent key should get the field from first item
        assert result["first_user_name"] == "Alice"

    def test_chained_transformations(self, test_webhook_service: WebhookService):
        """Test that transformations are applied in order."""
        body = {
            "user_id": "123",
            "user_name": "Alice Smith",
            "user_email": "alice@example.com",
        }

        rules = {
            "extract": {
                "id": "user_id",
                "name": "user_name",
                "email": "user_email"
            },
            "rename": {
                "id": "user_id"
            },
            "remove": ["email"]
        }

        result = test_webhook_service._apply_transform(body, rules)

        # Extract should happen first, then rename, then remove
        assert result == {
            "user_id": "123",
            "name": "Alice Smith"
        }

    def test_filter_with_extract(self, test_webhook_service: WebhookService):
        """Test filtering combined with extraction."""
        body = {
            "event": "payment.completed",
            "data": {
                "amount": 100,
                "currency": "USD"
            }
        }

        rules = {
            "filter_values": {"event": "payment.completed"},
            "extract": {
                "payment_amount": "data.amount",
                "payment_currency": "data.currency"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result["payment_amount"] == 100
        assert result["payment_currency"] == "USD"

    def test_null_handling(self, test_webhook_service: WebhookService):
        """Test handling of null/missing values."""
        body = {
            "id": 123,
            "name": None,
            "email": "test@example.com"
        }

        rules = {
            "extract": {
                "user_id": "id",
                "user_name": "name",
                "phone": "phone"
            }
        }

        result = test_webhook_service._apply_transform(body, rules)

        assert result["user_id"] == 123
        assert result["user_name"] is None
        assert result["phone"] is None


class TestCastValue:
    """Tests for the _cast_value method."""

    def test_cast_string(self, test_webhook_service: WebhookService):
        assert test_webhook_service._cast_value(123, "string") == "123"
        assert test_webhook_service._cast_value(True, "string") == "True"

    def test_cast_int(self, test_webhook_service: WebhookService):
        assert test_webhook_service._cast_value("42", "int") == 42
        assert test_webhook_service._cast_value(42.5, "int") == 42
        assert test_webhook_service._cast_value(42, "int") == 42

    def test_cast_float(self, test_webhook_service: WebhookService):
        assert test_webhook_service._cast_value("19.99", "float") == 19.99
        assert test_webhook_service._cast_value(19, "float") == 19.0

    def test_cast_bool(self, test_webhook_service: WebhookService):
        assert test_webhook_service._cast_value("true", "bool") is True
        assert test_webhook_service._cast_value("1", "bool") is True
        assert test_webhook_service._cast_value("yes", "bool") is True
        assert test_webhook_service._cast_value("false", "bool") is False
        assert test_webhook_service._cast_value("0", "bool") is False
        assert test_webhook_service._cast_value(1, "bool") is True
        assert test_webhook_service._cast_value(0, "bool") is False

    def test_cast_json(self, test_webhook_service: WebhookService):
        import json
        result = test_webhook_service._cast_value('{"key": "value"}', "json")
        assert result == {"key": "value"}

    def test_cast_invalid_json(self, test_webhook_service: WebhookService):
        # Should return original value if invalid
        result = test_webhook_service._cast_value("not json", "json")
        assert result == "not json"

    def test_cast_none(self, test_webhook_service: WebhookService):
        assert test_webhook_service._cast_value(None, "string") is None
        assert test_webhook_service._cast_value(None, "int") is None
