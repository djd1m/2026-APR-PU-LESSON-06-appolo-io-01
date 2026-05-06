import pytest


@pytest.mark.asyncio
async def test_create_company(auth_client):
    r = await auth_client.post("/api/v1/companies/", json={
        "name": "ТехноСофт", "inn": "7707083893", "region": "Москва", "employee_count": 150
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "ТехноСофт"
    assert data["inn"] == "7707083893"
    assert data["region"] == "Москва"


@pytest.mark.asyncio
async def test_get_company(auth_client):
    r = await auth_client.post("/api/v1/companies/", json={"name": "DataFlow"})
    cid = r.json()["id"]
    r2 = await auth_client.get(f"/api/v1/companies/{cid}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "DataFlow"


@pytest.mark.asyncio
async def test_get_company_not_found(auth_client):
    r = await auth_client.get("/api/v1/companies/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_search_companies_empty(auth_client):
    r = await auth_client.get("/api/v1/companies/search")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_search_companies_with_data(auth_client):
    await auth_client.post("/api/v1/companies/", json={"name": "Альфа", "region": "Москва", "employee_count": 100})
    await auth_client.post("/api/v1/companies/", json={"name": "Бета", "region": "СПб", "employee_count": 50})
    r = await auth_client.get("/api/v1/companies/search?region=Москва")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Альфа"


@pytest.mark.asyncio
async def test_search_companies_by_employee_count(auth_client):
    await auth_client.post("/api/v1/companies/", json={"name": "Big", "employee_count": 500})
    await auth_client.post("/api/v1/companies/", json={"name": "Small", "employee_count": 10})
    r = await auth_client.get("/api/v1/companies/search?employee_min=100")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Big"


@pytest.mark.asyncio
async def test_search_unauthorized(client):
    r = await client.get("/api/v1/companies/search")
    assert r.status_code == 401
