import pytest


@pytest.mark.asyncio
async def test_create_contact(auth_client):
    r = await auth_client.post("/api/v1/contacts/", json={
        "email": "petrov@technosoft.ru", "first_name": "Алексей", "last_name": "Петров",
        "title": "Head of Sales", "seniority": "director"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "petrov@technosoft.ru"
    assert data["first_name"] == "Алексей"


@pytest.mark.asyncio
async def test_create_contact_duplicate(auth_client):
    await auth_client.post("/api/v1/contacts/", json={"email": "dup@test.ru"})
    r = await auth_client.post("/api/v1/contacts/", json={"email": "dup@test.ru"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_contact(auth_client):
    r = await auth_client.post("/api/v1/contacts/", json={"email": "get@test.ru", "first_name": "Иван"})
    cid = r.json()["id"]
    r2 = await auth_client.get(f"/api/v1/contacts/{cid}")
    assert r2.status_code == 200
    assert r2.json()["first_name"] == "Иван"


@pytest.mark.asyncio
async def test_get_contact_not_found(auth_client):
    r = await auth_client.get("/api/v1/contacts/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_contacts(auth_client):
    await auth_client.post("/api/v1/contacts/", json={"email": "a@test.ru"})
    await auth_client.post("/api/v1/contacts/", json={"email": "b@test.ru"})
    r = await auth_client.get("/api/v1/contacts/")
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_score_contact(auth_client):
    r = await auth_client.post("/api/v1/contacts/", json={
        "email": "score@test.ru", "seniority": "c_level", "first_name": "CEO", "linkedin_url": "https://linkedin.com/in/ceo"
    })
    cid = r.json()["id"]
    r2 = await auth_client.post(f"/api/v1/contacts/{cid}/score")
    assert r2.status_code == 200
    data = r2.json()
    assert "score" in data
    assert "breakdown" in data
    assert data["version"] == "2.0"


@pytest.mark.asyncio
async def test_enrich_contact(auth_client):
    r = await auth_client.post("/api/v1/contacts/", json={"email": "enrich@test.ru"})
    cid = r.json()["id"]
    r2 = await auth_client.post(f"/api/v1/contacts/{cid}/enrich")
    assert r2.status_code == 200
    assert r2.json()["email_confidence"] == 0.85
    credits = await auth_client.get("/api/v1/billing/credits")
    assert credits.json()["credits"] == 49
