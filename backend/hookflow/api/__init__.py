"""HookFlow API dependencies and middleware."""

from hookflow.api.webhooks import router as webhooks_router

__all__ = ["webhooks_router"]
