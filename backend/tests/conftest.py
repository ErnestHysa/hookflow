import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from hookflow.models.base import Base
from hookflow.models.app import App, Webhook, Delivery, Destination, ApiKey


# Use SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create a test database engine"""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session"""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
