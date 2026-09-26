import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models import Base

TEST_DB_NAME = f"{settings.postgres_db}_test"
TEST_DB_URL = make_url(settings.database_url).set(database=TEST_DB_NAME)


async def _prepare_database() -> None:
    admin_engine = create_async_engine(
        TEST_DB_URL.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin_engine.dispose()

    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> None:
    asyncio.run(_prepare_database())


@pytest.fixture
async def session_factory() -> AsyncIterator[
    async_sessionmaker[AsyncSession]
]:
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE tickets, ticket_events RESTART IDENTITY CASCADE")
        )
    await engine.dispose()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def email_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr("app.api.tickets.send_status_changed_email", mock)
    return mock


@pytest.fixture
def ticket_payload() -> dict[str, Any]:
    return {
        "title": "VPN is not working",
        "description": "Client cannot connect after update",
        "customer_email": "ivanov@example.com",
        "priority": "high",
    }


@pytest.fixture
async def created_ticket(
    client: AsyncClient,
    ticket_payload: dict[str, Any],
) -> dict[str, Any]:
    response = await client.post("/api/v1/tickets", json=ticket_payload)
    assert response.status_code == 201
    return response.json()
