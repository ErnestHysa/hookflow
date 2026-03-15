"""API key management service."""

import hashlib
import secrets
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import ApiKey, App


class ApiKeyService:
    """Service for managing API keys."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_api_key(
        self,
        app_id: str,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, str]:
        """
        Create a new API key.

        Returns:
            Tuple of (ApiKey model, plain_text_key)
            The plain text key is only returned once!
        """
        # Generate key
        plain_key = f"hf_{secrets.token_urlsafe(32)}"
        key_prefix = plain_key[:10]
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

        api_key = ApiKey(
            app_id=app_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes or [],
            expires_at=expires_at,
        )

        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        return api_key, plain_key

    async def list_api_keys(self, app_id: str) -> list[ApiKey]:
        """List all API keys for an app (without full keys)."""
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.app_id == app_id)
            .where(ApiKey.is_active == True)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_api_key(self, api_key_id: str, app_id: str) -> bool:
        """Revoke an API key."""
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.app_id == app_id,
            )
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return False

        api_key.is_active = False
        await self.db.commit()
        return True

    async def validate_api_key(self, plain_key: str) -> ApiKey | None:
        """
        Validate an API key and update last_used_at.

        Returns:
            ApiKey if valid, None otherwise
        """
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key:
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
                return None

            # Update last used
            api_key.last_used_at = datetime.now(UTC)
            await self.db.commit()

        return api_key
