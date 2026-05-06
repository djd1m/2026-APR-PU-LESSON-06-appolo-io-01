import pytest


@pytest.mark.asyncio
async def test_hot_signals(auth_client):
    r = await auth_client.get("/api/v1/intents/hot")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "type" in data[0]
    assert "company" in data[0]


@pytest.mark.asyncio
async def test_company_signals(auth_client):
    r = await auth_client.get("/api/v1/intents/company/7707083893")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_analytics_overview(auth_client):
    r = await auth_client.get("/api/v1/analytics/overview")
    assert r.status_code == 200
    data = r.json()
    assert "companies" in data
    assert "contacts" in data
    assert "credits_remaining" in data
    assert data["credits_remaining"] == 50


@pytest.mark.asyncio
async def test_top_leads_empty(auth_client):
    r = await auth_client.get("/api/v1/analytics/top-leads")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_top_leads_with_scored_contacts(auth_client):
    r = await auth_client.post("/api/v1/contacts/", json={
        "email": "lead@test.ru", "seniority": "c_level", "first_name": "Top"
    })
    cid = r.json()["id"]
    await auth_client.post(f"/api/v1/contacts/{cid}/score")
    r2 = await auth_client.get("/api/v1/analytics/top-leads")
    assert r2.status_code == 200
    leads = r2.json()
    assert len(leads) == 1
    assert leads[0]["score"] > 0
