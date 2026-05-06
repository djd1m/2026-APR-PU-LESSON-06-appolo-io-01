import pytest


@pytest.mark.asyncio
async def test_list_plans(client):
    r = await client.get("/api/v1/billing/plans")
    assert r.status_code == 200
    data = r.json()
    assert "starter" in data
    assert "professional" in data
    assert "agency" in data


@pytest.mark.asyncio
async def test_get_credits(auth_client):
    r = await auth_client.get("/api/v1/billing/credits")
    assert r.status_code == 200
    data = r.json()
    assert data["credits"] == 50
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_upgrade_plan(auth_client):
    r = await auth_client.post("/api/v1/billing/upgrade", json={"plan": "starter"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["plan"] == "starter"
    assert data["credits_added"] == 500
    assert data["is_stub"] is True


@pytest.mark.asyncio
async def test_upgrade_unknown_plan(auth_client):
    r = await auth_client.post("/api/v1/billing/upgrade", json={"plan": "nonexistent"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_credits_after_upgrade(auth_client):
    await auth_client.post("/api/v1/billing/upgrade", json={"plan": "starter"})
    r = await auth_client.get("/api/v1/billing/credits")
    assert r.json()["credits"] == 550
    assert r.json()["plan"] == "starter"
