import pytest


@pytest.mark.asyncio
async def test_register(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com", "password": "pass123"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "new@example.com"
    assert data["plan"] == "free"
    assert data["credits"] == 50


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "pass123"})
    r = await client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "pass123"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": "pass123"})
    r = await client.post("/api/v1/auth/login", data={"username": "login@example.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={"email": "wrong@example.com", "password": "pass123"})
    r = await client.post("/api/v1/auth/login", data={"username": "wrong@example.com", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me(auth_client):
    r = await auth_client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_password_too_short(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "short@example.com", "password": "ab"
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_long(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "long@example.com", "password": "a" * 73
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_refresh_token(client):
    await client.post("/api/v1/auth/register", json={"email": "refresh@example.com", "password": "pass123"})
    r = await client.post("/api/v1/auth/login", data={"username": "refresh@example.com", "password": "pass123"})
    refresh = r.json()["refresh_token"]
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    assert "access_token" in r2.json()
