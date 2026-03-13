# HookFlow - Webhook-as-a-Service Platform

> Reliable webhook infrastructure for everyone.

## What is HookFlow?

HookFlow is a webhook infrastructure platform that handles receiving, storing, transforming, and delivering webhooks with guaranteed delivery and built-in retry logic.

### Problem It Solves

Every SaaS company needs to send webhooks. Every integrator needs to receive them. Building reliable webhook infrastructure is hard:

- **Retry logic** with exponential backoff
- **Idempotency** to prevent duplicate processing
- **Security** with HMAC signature verification
- **Dead letter queues** for failed events
- **Monitoring** and replay capabilities

HookFlow handles all of this so you don't have to.

## Features

- ✅ **Instant Setup** - Get a webhook URL in seconds
- ✅ **Guaranteed Delivery** - Automatic retries with exponential backoff
- ✅ **Signature Verification** - HMAC SHA-256 webhook signing
- ✅ **Idempotency** - Optional idempotency key support
- ✅ **Transformations** - JSON path extraction, filtering, flattening
- ✅ **Multiple Destinations** - HTTP, Slack, Discord, Database, etc.
- ✅ **Event Replay** - Replay webhooks to any destination
- ✅ **Full Visibility** - Real-time delivery status and logs

## Quick Start

### Using Docker (Recommended)

```bash
cd docker
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- Backend API on port 8000
- Frontend dashboard on port 3000

### Manual Setup

#### Backend

```bash
cd backend
pip install -e ".[dev]"
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost/hookflow"
export REDIS_URL="redis://localhost:6379/0"
uvicorn hookflow.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Usage

### 1. Create an App

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/apps \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "description": "Production webhooks"}'
```

Save the returned `webhook_secret` - you won't see it again!

### 2. Send a Webhook

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/{app_id} \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256={signature}" \
  -d '{"event": "user.created", "user_id": "12345"}'
```

### 3. Add a Destination

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/apps/{app_id}/destinations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API",
    "type": "http",
    "config": {"url": "https://api.example.com/webhook"}
  }'
```

### 4. View Webhooks

```bash
curl http://localhost:8000/api/v1/webhooks/{app_id}
```

## Project Structure

```
hookflow/
├── backend/           # FastAPI backend
│   ├── hookflow/
│   │   ├── api/      # API routes
│   │   ├── core/     # Config, database, redis
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   ├── services/ # Business logic
│   │   └── workers/  # Background workers
│   └── tests/        # Tests
├── frontend/          # Next.js dashboard
│   ├── src/
│   │   ├── app/      # Next.js 14 app router
│   │   ├── components/
│   │   └── lib/      # Utilities
│   └── public/
├── docker/            # Docker configuration
│   └── docker-compose.yml
└── README.md
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Dashboard: http://localhost:3000

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT secret key | - |
| `ENVIRONMENT` | environment | `development` |

## Roadmap

- [ ] OAuth/OIDC authentication
- [ ] Webhook templates marketplace
- [ ] AI-powered data transformation
- [ ] Scheduled webhooks (cron)
- [ ] Webhook debugging proxy
- [ ] Custom webhook domains
- [ ] Self-hosted version
- [ ] CLI tool
- [ ] SDKs (Python, Node.js, Go)

## Contributing

Contributions welcome! Please read our contributing guidelines.

## License

MIT License - see LICENSE for details.

---

Built with ❤️ by the HookFlow team
