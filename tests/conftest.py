import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["OPENAI_API_KEY"] = ""
os.environ["DEBUG"] = "false"
os.environ["PAYMENTS_STUB"] = "true"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from models.database import create_tables, drop_tables


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await create_tables()
    yield
    await drop_tables()
    from routers.auth import _rate_limit_store
    _rate_limit_store.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com", "password": "testpass123", "full_name": "Test User"
    })
    form = {"username": "test@example.com", "password": "testpass123"}
    r = await client.post("/api/v1/auth/login", data=form)
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
