import pytest


async def _setup_enrollment(auth_client):
    """Create a contact, sequence with 2 steps, and return their IDs."""
    c = await auth_client.post("/api/v1/contacts/", json={"email": "enroll@test.ru"})
    contact_id = c.json()["id"]

    s = await auth_client.post("/api/v1/sequences/", json={
        "name": "Enroll Seq",
        "steps": [
            {"step_order": 1, "subject_template": "S1", "body_template": "B1", "delay_days": 0},
            {"step_order": 2, "subject_template": "S2", "body_template": "B2", "delay_days": 2},
        ]
    })
    sequence_id = s.json()["id"]
    return contact_id, sequence_id


@pytest.mark.asyncio
async def test_enroll_contact(auth_client):
    cid, sid = await _setup_enrollment(auth_client)
    r = await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "active"
    assert data["current_step"] == 1


@pytest.mark.asyncio
async def test_enroll_duplicate(auth_client):
    cid, sid = await _setup_enrollment(auth_client)
    await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    r = await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_advance_enrollment(auth_client):
    cid, sid = await _setup_enrollment(auth_client)
    r = await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    eid = r.json()["id"]

    r2 = await auth_client.post(f"/api/v1/enrollments/{eid}/advance")
    assert r2.status_code == 200
    assert r2.json()["current_step"] == 2
    assert r2.json()["status"] == "active"


@pytest.mark.asyncio
async def test_advance_to_completion(auth_client):
    cid, sid = await _setup_enrollment(auth_client)
    r = await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    eid = r.json()["id"]

    await auth_client.post(f"/api/v1/enrollments/{eid}/advance")
    r3 = await auth_client.post(f"/api/v1/enrollments/{eid}/advance")
    assert r3.json()["status"] == "completed"
    assert r3.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_update_enrollment_status(auth_client):
    cid, sid = await _setup_enrollment(auth_client)
    r = await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    eid = r.json()["id"]

    r2 = await auth_client.put(f"/api/v1/enrollments/{eid}/status", json={"status": "paused"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_list_enrollments(auth_client):
    cid, sid = await _setup_enrollment(auth_client)
    await auth_client.post("/api/v1/enrollments/", json={"contact_id": cid, "sequence_id": sid})
    r = await auth_client.get("/api/v1/enrollments/")
    assert r.status_code == 200
    assert len(r.json()) == 1
