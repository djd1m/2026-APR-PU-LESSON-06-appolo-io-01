import pytest


@pytest.mark.asyncio
async def test_create_sequence(auth_client):
    r = await auth_client.post("/api/v1/sequences/", json={
        "name": "Cold Outreach", "description": "Initial outreach sequence"
    })
    assert r.status_code == 201
    assert r.json()["name"] == "Cold Outreach"
    assert r.json()["is_active"] is True


@pytest.mark.asyncio
async def test_create_sequence_with_steps(auth_client):
    r = await auth_client.post("/api/v1/sequences/", json={
        "name": "Follow-up",
        "steps": [
            {"step_order": 1, "subject_template": "Hi {first_name}", "body_template": "Body 1", "delay_days": 0},
            {"step_order": 2, "subject_template": "Follow-up", "body_template": "Body 2", "delay_days": 3},
        ]
    })
    assert r.status_code == 201
    sid = r.json()["id"]
    detail = await auth_client.get(f"/api/v1/sequences/{sid}")
    assert len(detail.json()["steps"]) == 2


@pytest.mark.asyncio
async def test_list_sequences(auth_client):
    await auth_client.post("/api/v1/sequences/", json={"name": "Seq A"})
    await auth_client.post("/api/v1/sequences/", json={"name": "Seq B"})
    r = await auth_client.get("/api/v1/sequences/")
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_get_sequence_not_found(auth_client):
    r = await auth_client.get("/api/v1/sequences/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_toggle_sequence(auth_client):
    r = await auth_client.post("/api/v1/sequences/", json={"name": "Toggle Me"})
    sid = r.json()["id"]
    r2 = await auth_client.patch(f"/api/v1/sequences/{sid}/toggle")
    assert r2.status_code == 200
    assert r2.json()["is_active"] is False
    r3 = await auth_client.patch(f"/api/v1/sequences/{sid}/toggle")
    assert r3.json()["is_active"] is True


@pytest.mark.asyncio
async def test_add_step(auth_client):
    r = await auth_client.post("/api/v1/sequences/", json={"name": "Step Test"})
    sid = r.json()["id"]
    r2 = await auth_client.post(f"/api/v1/sequences/{sid}/steps", json={
        "step_order": 1, "subject_template": "Subj", "body_template": "Body", "delay_days": 1
    })
    assert r2.status_code == 201
    assert r2.json()["step_order"] == 1
