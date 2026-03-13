# HookFlow Backend

FastAPI-based backend for HookFlow webhook infrastructure platform.

## Development Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start development server
uvicorn hookflow.main:app --reload --port 8000
```

## Environment Variables

Create a `.env` file:

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/hookflow
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
ENVIRONMENT=development
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
