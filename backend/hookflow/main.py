"""HookFlow - Webhook-as-a-Service Platform."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

from hookflow.api import webhooks_router
from hookflow.api.analytics import router as analytics_router
from hookflow.api.api_keys import router as api_keys_router
from hookflow.api.events import router as events_router
from hookflow.api.v1.auth import router as auth_router
from hookflow.api.v1.users import router as users_router
from hookflow.core.config import settings
from hookflow.core.database import close_db, init_db
from hookflow.core.queue import queue_client
from hookflow.workers import start_retry_worker, stop_retry_worker, start_worker, stop_worker

# Metrics
webhook_received = Counter(
    "hookflow_webhooks_received_total",
    "Total webhooks received",
    ["app_id"],
)
webhook_delivered = Counter(
    "hookflow_webhooks_delivered_total",
    "Total webhooks delivered successfully",
    ["app_id", "destination_type"],
)
webhook_failed = Counter(
    "hookflow_webhooks_failed_total",
    "Total webhooks failed to deliver",
    ["app_id", "destination_type", "error_type"],
)
http_request_duration = Histogram(
    "hookflow_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint", "status"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""

    # Startup
    print("Starting HookFlow...")
    print(f"Environment: {settings.environment}")
    print(f"Debug: {settings.debug}")

    # Initialize queue (in-memory for local dev)
    await queue_client.connect()
    print("Queue connected")

    # Initialize database
    await init_db()
    print("Database initialized")

    # Start background workers
    print("Starting delivery worker...")
    await start_worker()
    print("Delivery worker started")

    print("Starting retry worker...")
    await start_retry_worker()
    print("Retry worker started")

    print("HookFlow ready!")

    yield

    # Shutdown
    print("Shutting down HookFlow...")
    await stop_worker()
    await stop_retry_worker()
    await queue_client.disconnect()
    await close_db()
    print("HookFlow stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## HookFlow - Webhook-as-a-Service Platform

Reliable webhook infrastructure for everyone.

### Features

- **Reliable Delivery**: Automatic retries with exponential backoff
- **Dead Letter Queue**: View and manage failed deliveries
- **Event Transformation**: Filter, extract, and transform webhook payloads
- **Rate Limiting**: Per-app monthly limits with configurable quotas
- **Real-time Events**: Server-Sent Events for live delivery updates
- **Multiple Destinations**: HTTP, Slack, Discord, Telegram, Email, Database, Notion, Airtable, Google Sheets

### Authentication

API requests are authenticated using API keys. Include your API key in the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" https://api.hookflow.dev/api/v1/apps
```

### Rate Limiting

Each app has a monthly webhook limit. When the limit is exceeded, webhooks will return a `429 Too Many Requests` response.

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Your monthly limit
- `X-RateLimit-Remaining`: Remaining webhooks this month
- `X-RateLimit-Reset`: Unix timestamp when the limit resets

### Webhook Signature

HookFlow signs all outgoing webhook deliveries using HMAC SHA256. The signature is included in the `X-Webhook-Signature` header.

Format: `t={timestamp},v1={signature}`

### Status Codes

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `202 Accepted`: Webhook accepted for processing
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid API key
- `403 Forbidden`: Access denied
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Support

For help, visit [docs.hookflow.dev](https://docs.hookflow.dev) or email support@hookflow.dev
    """,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
    tags=[
        {
            "name": "webhooks",
            "description": "Webhook receiving, processing, and management",
        },
        {
            "name": "apps",
            "description": "Application management and configuration",
        },
        {
            "name": "destinations",
            "description": "Webhook destination configuration and testing",
        },
        {
            "name": "analytics",
            "description": "Webhook analytics and statistics",
        },
        {
            "name": "api-keys",
            "description": "API key management",
        },
        {
            "name": "dead-letter-queue",
            "description": "Failed delivery management",
        },
        {
            "name": "health",
            "description": "Health check and monitoring endpoints",
        },
        {
            "name": "metrics",
            "description": "Prometheus metrics endpoint",
        },
    ],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


# Metrics endpoint
@app.get("/metrics", tags=["metrics"])
async def metrics() -> Response:
    """Prometheus metrics endpoint."""

    return Response(generate_latest(), media_type="text/plain")


# Include routers
app.include_router(webhooks_router, prefix=settings.api_prefix)
app.include_router(analytics_router, prefix=settings.api_prefix)
app.include_router(api_keys_router, prefix=settings.api_prefix)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": exc.detail,
            "code": f"HTTP_{exc.status_code}",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""

    import logging
    import traceback

    logging.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "detail": "An internal error occurred" if settings.is_production else str(exc),
            "code": "INTERNAL_ERROR",
        },
    )


# Middleware for request timing
@app.middleware("http")
async def timing_middleware(request: Request, call_next) -> Response:
    """Measure request duration for metrics."""

    import time

    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    http_request_duration.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).observe(duration)

    # Add timing header
    response.headers["X-Response-Time"] = f"{duration*1000:.2f}ms"

    return response


# Root endpoint
@app.get("/", tags=["root"])
async def root() -> dict[str, str | dict[str, str]]:
    """Root endpoint with API information."""

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.is_development else None,
        "health": "/health",
        "metrics": "/metrics",
        "api": {
            "v1": settings.api_prefix,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "hookflow.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
