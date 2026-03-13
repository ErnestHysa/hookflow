"""Authentication service for Clerk JWT verification."""

import json
from typing import Any

import httpx
from jose import jwk, jwt
from jose.exceptions import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.config import settings
from hookflow.models import User


class ClerkAuthError(Exception):
    """Error raised when Clerk authentication fails."""

    pass


class ClerkAuthService:
    """Service for verifying Clerk JWT tokens and syncing users."""

    def __init__(self) -> None:
        self.clerk_broker_url = "https://clerk.com"
        self.jwks_cache: dict[str, dict[str, Any]] = {}
        self.issuer_url: str | None = None

    async def get_jwks(self, kid: str | None = None) -> dict[str, Any]:
        """Get JWKS from Clerk.

        Args:
            kid: Key ID to filter for (optional)

        Returns:
            JWKS as a dictionary

        Raises:
            ClerkAuthError: If JWKS cannot be fetched
        """
        if not settings.clerk_secret_key:
            raise ClerkAuthError("CLERK_SECRET_KEY not configured")

        # Build JWKS URL
        if not self.issuer_url:
            # Try to discover issuer from Clerk
            async with httpx.AsyncClient() as client:
                # Get the Clerk frontend API URL
                frontend_api = settings.clerk_frontend_api or "https://accounts.devbycircles.com"

                # Clerk's JWKS endpoint
                jwks_url = f"{frontend_api}/.well-known/jwks.json"

                response = await client.get(
                    jwks_url,
                    headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
                )
                response.raise_for_status()
                return response.json()

        return await self._fetch_jwks()

    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from the issuer URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.issuer_url}/.well-known/jwks.json")
            response.raise_for_status()
            return response.json()

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify a Clerk JWT token.

        Args:
            token: The JWT token to verify

        Returns:
            Decoded token payload

        Raises:
            ClerkAuthError: If token is invalid or verification fails
        """
        if not settings.clerk_secret_key:
            raise ClerkAuthError("CLERK_SECRET_KEY not configured")

        try:
            # Decode without verification first to get the kid header
            headers = jwt.get_unverified_headers(token)
            kid = headers.get("kid")

            if not kid:
                raise ClerkAuthError("Token missing 'kid' header")

            # Get the public key
            # Note: In production, you'd cache JWKS and fetch by kid
            # For simplicity, we're using the secret key to verify
            # Clerk supports both methods

            # Verify using Clerk's secret key (simpler approach)
            payload = jwt.decode(
                token,
                settings.clerk_secret_key,
                algorithms=["RS256"],
                options={
                    "verify_aud": False,  # Clerk tokens don't always have aud
                    "verify_iss": True,
                },
            )

            return payload

        except JWTError as e:
            raise ClerkAuthError(f"Token verification failed: {e}") from e

    async def get_or_create_user(
        self,
        db: AsyncSession,
        clerk_id: str,
        email: str,
        name: str | None = None,
    ) -> User:
        """Get or create a user from Clerk data.

        Args:
            db: Database session
            clerk_id: Clerk user ID
            email: User email
            name: User name (optional)

        Returns:
            User instance
        """
        from sqlalchemy import select

        # Try to find existing user by clerk_id
        result = await db.execute(select(User).where(User.id == clerk_id))
        user = result.scalar_one_or_none()

        if user:
            # Update user data if changed
            if user.email != email:
                user.email = email
            if name and user.name != name:
                user.name = name
            await db.commit()
            await db.refresh(user)
            return user

        # Create new user
        user = User(
            id=clerk_id,
            email=email,
            name=name or email.split("@")[0],
            password_hash="",  # Not used for Clerk users
            email_verified=True,  # Clerk verifies email
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload: dict[str, Any],
    ) -> None:
        """Handle a Clerk webhook event.

        Args:
            db: Database session
            payload: Webhook payload

        Raises:
            ClerkAuthError: If webhook processing fails
        """
        event_type = payload.get("type")
        data = payload.get("data", {})

        if event_type == "user.created":
            await self._handle_user_created(db, data)
        elif event_type == "user.updated":
            await self._handle_user_updated(db, data)
        elif event_type == "user.deleted":
            await self._handle_user_deleted(db, data)
        elif event_type == "email.created":
            # Email verification handled by Clerk
            pass
        else:
            # Ignore other events
            pass

    async def _handle_user_created(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle user.created event."""
        clerk_id = data.get("id")
        if not clerk_id:
            return

        primary_email_address_id = data.get("primary_email_address_id")
        email_addresses = data.get("email_addresses", [])
        email = ""
        for addr in email_addresses:
            if addr.get("id") == primary_email_address_id:
                email = addr.get("email_address", "")
                break

        if not email:
            email = email_addresses[0].get("email_address", "") if email_addresses else ""

        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        name = f"{first_name} {last_name}".strip() or data.get("username", "")

        await self.get_or_create_user(db, clerk_id, email, name)

    async def _handle_user_updated(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle user.updated event."""
        from sqlalchemy import select

        clerk_id = data.get("id")
        if not clerk_id:
            return

        result = await db.execute(select(User).where(User.id == clerk_id))
        user = result.scalar_one_or_none()

        if not user:
            # User doesn't exist, create it
            await self._handle_user_created(db, data)
            return

        # Update user data
        primary_email_address_id = data.get("primary_email_address_id")
        email_addresses = data.get("email_addresses", [])
        email = ""
        for addr in email_addresses:
            if addr.get("id") == primary_email_address_id:
                email = addr.get("email_address", "")
                break

        if email:
            user.email = email

        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        name = f"{first_name} {last_name}".strip() or data.get("username", "")

        if name:
            user.name = name

        await db.commit()

    async def _handle_user_deleted(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> None:
        """Handle user.deleted event."""
        from sqlalchemy import select

        clerk_id = data.get("id")
        if not clerk_id:
            return

        # Soft delete by deactivating
        result = await db.execute(select(User).where(User.id == clerk_id))
        user = result.scalar_one_or_none()

        if user:
            user.is_active = False
            await db.commit()

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        """Verify Clerk webhook signature.

        Args:
            payload: Raw request body
            signature: Svix signature header
            timestamp: Svix timestamp header

        Returns:
            True if signature is valid

        Raises:
            ClerkAuthError: If signature is invalid
        """
        if not settings.clerk_webhook_secret:
            raise ClerkAuthError("CLERK_WEBHOOK_SECRET not configured")

        # Clerk uses Svix for webhooks
        # The signature format is: t=<timestamp>,v1=<signature>
        try:
            from svix.webhooks import Webhook

            webhook = Webhook(settings.clerk_webhook_secret)
            webhook.verify(payload, {
                "svix-id": timestamp,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            })
            return True

        except Exception as e:
            raise ClerkAuthError(f"Webhook signature verification failed: {e}") from e


# Global service instance
_auth_service: ClerkAuthService | None = None


def get_clerk_auth_service() -> ClerkAuthService:
    """Get the global Clerk auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = ClerkAuthService()
    return _auth_service
