"""API key management endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db
from hookflow.services.api_key import ApiKeyService

router = APIRouter(prefix="/apps", tags=["api-keys"])


class ApiKeyCreateRequest(BaseModel):
    """Request to create API key."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyCreateResponse(BaseModel):
    """Response when creating API key (includes full key)."""

    id: str
    name: str
    key: str  # Full key - only shown once!
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Response when listing API keys (no full key)."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


async def get_api_key_service(
    db: AsyncSession = Depends(get_db),
) -> ApiKeyService:
    """Get API key service instance."""
    return ApiKeyService(db)


@router.post(
    "/{app_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    app_id: str,
    request: ApiKeyCreateRequest,
    service: ApiKeyService = Depends(get_api_key_service),
):
    """Create a new API key. Returns the full key - save it now!"""
    api_key, plain_key = await service.create_api_key(
        app_id=app_id,
        name=request.name,
        scopes=request.scopes,
        expires_at=request.expires_at,
    )

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,  # Only shown once!
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/{app_id}/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    app_id: str,
    service: ApiKeyService = Depends(get_api_key_service),
):
    """List all API keys for an app (full keys not shown)."""
    api_keys = await service.list_api_keys(app_id)

    return [
        ApiKeyResponse(
            id=key.id,
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
            created_at=key.created_at,
        )
        for key in api_keys
    ]


@router.delete(
    "/{app_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    app_id: str,
    key_id: str,
    service: ApiKeyService = Depends(get_api_key_service),
):
    """Revoke an API key."""
    success = await service.revoke_api_key(key_id, app_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
