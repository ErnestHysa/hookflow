import pytest
import secrets
from datetime import datetime, timedelta
from hookflow.services.api_key import ApiKeyService
from hookflow.models.app import App, ApiKey
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_api_key(db_session: AsyncSession):
    """Test creating a new API key"""
    app = App(
        id="test-app-1",
        name="Test App",
        user_id="test-user-1",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    service = ApiKeyService(db_session)
    
    api_key, plain_key = await service.create_api_key(
        app_id=app.id,
        name="Test Key",
        scopes=["read", "write"],
    )

    assert api_key.name == "Test Key"
    assert api_key.scopes == ["read", "write"]
    assert plain_key.startswith("hf_")
    assert len(plain_key) > 40  # hf_ prefix + 32 bytes base64 ≈ 43 chars


@pytest.mark.asyncio
async def test_create_api_key_with_expiration(db_session: AsyncSession):
    """Test creating API key with expiration"""
    app = App(
        id="test-app-2",
        name="Test App 2",
        user_id="test-user-2",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    service = ApiKeyService(db_session)
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    api_key, plain_key = await service.create_api_key(
        app_id=app.id,
        name="Expiring Key",
        scopes=["read"],
        expires_at=expires_at,
    )

    assert api_key.expires_at is not None


@pytest.mark.asyncio
async def test_list_api_keys(db_session: AsyncSession):
    """Test listing API keys for an app"""
    app = App(
        id="test-app-3",
        name="Test App 3",
        user_id="test-user-3",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    service = ApiKeyService(db_session)

    # Create multiple keys
    await service.create_api_key(app.id, "Key 1", ["read"])
    await service.create_api_key(app.id, "Key 2", ["write"])

    keys = await service.list_api_keys(app.id)

    assert len(keys) == 2
    assert any(k.name == "Key 1" for k in keys)
    assert any(k.name == "Key 2" for k in keys)


@pytest.mark.asyncio
async def test_revoke_api_key(db_session: AsyncSession):
    """Test revoking an API key"""
    app = App(
        id="test-app-4",
        name="Test App 4",
        user_id="test-user-4",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    service = ApiKeyService(db_session)

    # Create a key
    api_key, _ = await service.create_api_key(app.id, "To Revoke", ["read"])
    key_id = api_key.id

    # Revoke it
    result = await service.revoke_api_key(key_id, app.id)
    assert result is True

    # Verify it's gone from list
    keys = await service.list_api_keys(app.id)
    assert len(keys) == 0


@pytest.mark.asyncio
async def test_validate_api_key(db_session: AsyncSession):
    """Test validating an API key"""
    app = App(
        id="test-app-5",
        name="Test App 5",
        user_id="test-user-5",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    service = ApiKeyService(db_session)

    # Create a key
    api_key, plain_key = await service.create_api_key(
        app.id, "Valid Key", ["read", "write"]
    )

    # Validate it
    key_record = await service.validate_api_key(plain_key)

    assert key_record is not None
    assert key_record.app_id == app.id
    assert key_record.scopes == ["read", "write"]


@pytest.mark.asyncio
async def test_validate_invalid_api_key(db_session: AsyncSession):
    """Test validating an invalid API key"""
    app = App(
        id="test-app-6",
        name="Test App 6",
        user_id="test-user-6",
        webhook_secret="test-secret",
        monthly_limit=10000
    )
    db_session.add(app)
    await db_session.commit()

    service = ApiKeyService(db_session)

    # Try to validate a non-existent key
    key_record = await service.validate_api_key("hf_invalidkey123456789")

    assert key_record is None
