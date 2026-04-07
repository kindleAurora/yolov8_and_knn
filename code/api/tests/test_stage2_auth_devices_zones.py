from __future__ import annotations


def login(client, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_me_returns_current_user(client) -> None:
    token = login(client, "admin", "admin123")

    response = client.get("/api/v1/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["username"] == "admin"
    assert payload["roles"] == ["admin"]


def test_viewer_cannot_create_device(client) -> None:
    token = login(client, "viewer", "viewer123")

    response = client.post(
        "/api/v1/devices",
        json={
            "code": "CAM-NEW-001",
            "name": "New Camera",
            "device_type": "camera",
            "stream_url": "rtsp://test/new-cam",
            "install_location": "Yard B",
            "status": "online",
            "is_enabled": True,
            "config": {"resolution": "720p"},
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_admin_can_create_and_disable_device(client) -> None:
    token = login(client, "admin", "admin123")

    create_response = client.post(
        "/api/v1/devices",
        json={
            "code": "CAM-NEW-002",
            "name": "New Camera",
            "device_type": "camera",
            "stream_url": "rtsp://test/new-cam",
            "install_location": "Yard B",
            "status": "online",
            "is_enabled": True,
            "config": {"resolution": "720p"},
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    device = create_response.json()["data"]

    patch_response = client.patch(
        f"/api/v1/devices/{device['id']}/status",
        json={"status": "disabled", "is_enabled": False},
        headers=auth_headers(token),
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["is_enabled"] is False


def test_authenticated_user_can_crud_zone(client) -> None:
    token = login(client, "viewer", "viewer123")

    create_response = client.post(
        "/api/v1/zones",
        json={
            "device_id": 1,
            "name": "Rest Area",
            "zone_type": "rest",
            "shape_type": "polygon",
            "points": [
                {"x": 0.2, "y": 0.2},
                {"x": 0.5, "y": 0.2},
                {"x": 0.45, "y": 0.45},
            ],
            "is_enabled": True,
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    zone = create_response.json()["data"]

    update_response = client.put(
        f"/api/v1/zones/{zone['id']}",
        json={
            "device_id": 1,
            "name": "Rest Area Updated",
            "zone_type": "rest",
            "shape_type": "polygon",
            "points": [
                {"x": 0.25, "y": 0.25},
                {"x": 0.55, "y": 0.25},
                {"x": 0.5, "y": 0.5},
            ],
            "is_enabled": False,
        },
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["name"] == "Rest Area Updated"
    assert update_response.json()["data"]["is_enabled"] is False

    delete_response = client.delete(f"/api/v1/zones/{zone['id']}", headers=auth_headers(token))
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["deleted"] is True
