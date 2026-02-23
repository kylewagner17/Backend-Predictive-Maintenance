"""
API endpoint tests. Uses client and db fixtures from conftest.py.
Run with: pytest test_api.py -v
"""


def test_health_returns_ok(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "backend running"}


def test_devices_list_empty(client):
    response = client.get("/devices/")
    assert response.status_code == 200
    assert response.json() == []


def test_devices_list_after_create(client, db):
    from app import crud, schemas
    crud.create_device(db, schemas.DeviceCreate(name="TestDevice"))
    response = client.get("/devices/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "TestDevice"
    assert "id" in data[0]
    assert data[0]["status"] == "OK"


def test_sensor_reading_create_and_get(client, db):
    from app import crud, schemas
    dev = crud.create_device(db, schemas.DeviceCreate(name="Sensor1"))
    # POST reading via API
    r = client.post(
        "/sensors/reading",
        json={"device_id": dev.id, "reading": 42.5, "status": "OK"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reading"] == 42.5
    assert body["device_id"] == dev.id
    assert "id" in body
    assert "timestamp" in body
    # GET readings for device
    r2 = client.get(f"/sensors/readings/{dev.id}")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["reading"] == 42.5


def test_analysis_run_returns_ok(client, db):
    response = client.post("/analysis/run")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_device_predictions_empty(client, db):
    from app import crud, schemas
    dev = crud.create_device(db, schemas.DeviceCreate(name="D1"))
    response = client.get(f"/devices/{dev.id}/predictions")
    assert response.status_code == 200
    assert response.json() == []


def test_notifications_subscribe_email(client, db):
    response = client.post(
        "/notifications/subscribe-email",
        json={"email": "test@example.com", "device_id": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["device_id"] is None
    assert "id" in data
    assert "created_at" in data


def test_notifications_subscribe_push(client, db):
    response = client.post(
        "/notifications/subscribe",
        json={"token": "fake-fcm-token", "device_id": None, "platform": "android"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "fake-fcm-token"
    assert data["platform"] == "android"
    assert "id" in data
