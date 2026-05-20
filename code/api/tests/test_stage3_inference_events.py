from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.models import BehaviorEvent, MediaAsset


def login(client, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_import_behavior_events_persists_records(client, db_session, monkeypatch) -> None:
    captured_payload: dict[str, object] = {}

    def fake_inference_service(payload: dict[str, object], **_kwargs) -> dict[str, object]:
        captured_payload.update(payload)
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        return {
            "request_id": payload["request_id"],
            "service": "cow-monitor-inference",
            "model_name": "yolo-knn-stage3-demo",
            "model_version": "0.3.0",
            "inference_source": "demo-pipeline",
            "processed_at": datetime.now(UTC).isoformat(),
            "behavior_events": [
                {
                    "device_code": payload["device_code"],
                    "event_time": occurred_at.isoformat(),
                    "behavior_type": "standing",
                    "cow_count": 5,
                    "confidence": 0.92,
                    "zone_name": "Water Zone",
                    "notes": "测试导入事件一",
                },
                {
                    "device_code": payload["device_code"],
                    "event_time": (occurred_at + timedelta(seconds=18)).isoformat(),
                    "behavior_type": "drinking",
                    "cow_count": 3,
                    "confidence": 0.87,
                    "zone_name": "Water Zone",
                    "notes": "测试导入事件二",
                },
            ],
            "raw_metadata": {
                "pipeline_mode": "demo",
                "source_type": payload["source_type"],
            },
        }

    monkeypatch.setattr(
        "app.modules.events.router.invoke_inference_service",
        fake_inference_service,
    )

    token = login(client, "viewer", "viewer123")
    occurred_at = datetime.now(UTC)

    response = client.post(
        "/api/v1/events/import",
        json={
            "device_code": "CAM-TEST-001",
            "source_type": "video",
            "source_uri": "demo://tests/sample-video.mp4",
            "occurred_at": occurred_at.isoformat(),
            "metadata": {},
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["imported_count"] == 2
    assert payload["model_name"] == "yolo-knn-stage3-demo"
    assert payload["behavior_events"][0]["device_code"] == "CAM-TEST-001"

    assert db_session.query(BehaviorEvent).count() == 2
    assert db_session.query(MediaAsset).count() == 1

    first_event = db_session.query(BehaviorEvent).order_by(BehaviorEvent.id.asc()).first()
    assert first_event is not None
    assert first_event.model_version == "0.3.0"
    assert first_event.zone_name == "Water Zone"

    metadata = captured_payload["metadata"]
    assert isinstance(metadata, dict)
    zone_candidates = metadata["zone_candidates"]
    assert isinstance(zone_candidates, list)
    assert zone_candidates[0]["name"] == "Water Zone"
    assert zone_candidates[0]["zone_type"] == "water"
    assert zone_candidates[0]["shape_type"] == "polygon"
    assert len(zone_candidates[0]["points"]) >= 3


def test_behavior_event_summary_and_filters(client, monkeypatch) -> None:
    def fake_inference_service(payload: dict[str, object], **_kwargs) -> dict[str, object]:
        return {
            "request_id": payload["request_id"],
            "service": "cow-monitor-inference",
            "model_name": "yolo-knn-stage3-demo",
            "model_version": "0.3.0",
            "inference_source": "demo-pipeline",
            "processed_at": datetime.now(UTC).isoformat(),
            "behavior_events": [
                {
                    "device_code": payload["device_code"],
                    "event_time": payload["occurred_at"],
                    "behavior_type": "feeding",
                    "cow_count": 4,
                    "confidence": 0.9,
                    "zone_name": "Water Zone",
                    "notes": None,
                }
            ],
            "raw_metadata": {"pipeline_mode": "demo"},
        }

    monkeypatch.setattr(
        "app.modules.events.router.invoke_inference_service",
        fake_inference_service,
    )

    token = login(client, "admin", "admin123")

    import_response = client.post(
        "/api/v1/events/import",
        json={
            "device_code": "CAM-TEST-001",
            "source_type": "image",
            "source_uri": "demo://tests/sample-image.jpg",
            "occurred_at": datetime.now(UTC).isoformat(),
            "frame_uri": "demo://tests/frame-001.jpg",
            "metadata": {},
        },
        headers=auth_headers(token),
    )
    assert import_response.status_code == 200

    summary_response = client.get("/api/v1/events/summary", headers=auth_headers(token))
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()["data"]
    assert summary_payload["total_count"] == 1
    assert summary_payload["today_count"] == 1
    assert len(summary_payload["recent_events"]) == 1
    assert summary_payload["today_behavior_overview"]["total_events"] == 1
    assert isinstance(summary_payload["today_behavior_overview"]["breakdown"], list)

    list_response = client.get(
        "/api/v1/events?behavior_type=feeding&limit=10",
        headers=auth_headers(token),
    )
    assert list_response.status_code == 200
    listed_events = list_response.json()["data"]
    assert len(listed_events) == 1
    assert listed_events[0]["behavior_type"] == "feeding"


def test_behavior_event_summary_includes_daily_state_overview(client, monkeypatch) -> None:
    def fake_inference_service(payload: dict[str, object], **_kwargs) -> dict[str, object]:
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        return {
            "request_id": payload["request_id"],
            "service": "cow-monitor-inference",
            "model_name": "yolo-knn-stage3-demo",
            "model_version": "0.3.0",
            "inference_source": "demo-pipeline",
            "processed_at": datetime.now(UTC).isoformat(),
            "behavior_events": [
                {
                    "device_code": payload["device_code"],
                    "event_time": occurred_at.isoformat(),
                    "behavior_type": "standing",
                    "cow_count": 3,
                    "confidence": 0.94,
                    "zone_name": "Water Zone",
                    "notes": None,
                },
                {
                    "device_code": payload["device_code"],
                    "event_time": (occurred_at + timedelta(minutes=10)).isoformat(),
                    "behavior_type": "lying",
                    "cow_count": 2,
                    "confidence": 0.91,
                    "zone_name": "Rest Zone",
                    "notes": None,
                },
                {
                    "device_code": payload["device_code"],
                    "event_time": (occurred_at + timedelta(minutes=20)).isoformat(),
                    "behavior_type": "feeding",
                    "cow_count": 4,
                    "confidence": 0.89,
                    "zone_name": "Feed Zone",
                    "notes": None,
                },
            ],
            "raw_metadata": {"pipeline_mode": "demo"},
        }

    monkeypatch.setattr(
        "app.modules.events.router.invoke_inference_service",
        fake_inference_service,
    )

    token = login(client, "admin", "admin123")
    occurred_at = datetime.now(UTC) - timedelta(minutes=30)

    import_response = client.post(
        "/api/v1/events/import",
        json={
            "device_code": "CAM-TEST-001",
            "source_type": "video",
            "source_uri": "demo://tests/sample-video.mp4",
            "occurred_at": occurred_at.isoformat(),
            "metadata": {},
        },
        headers=auth_headers(token),
    )
    assert import_response.status_code == 200

    summary_response = client.get(
        "/api/v1/events/summary?device_id=1",
        headers=auth_headers(token),
    )
    assert summary_response.status_code == 200

    overview = summary_response.json()["data"]["today_behavior_overview"]
    assert overview["total_events"] == 3
    assert overview["lying_event_count"] == 1
    assert overview["standing_duration_seconds"] == 600
    assert len(overview["timeline"]) >= 3
    assert any(item["behavior_key"] == "standing" for item in overview["breakdown"])
    assert any(item["behavior_key"] == "lying" for item in overview["breakdown"])


def test_media_preview_and_source_proxy(client, monkeypatch) -> None:
    def fake_inference_service(payload: dict[str, object], **_kwargs) -> dict[str, object]:
        return {
            "request_id": payload["request_id"],
            "service": "cow-monitor-inference",
            "model_name": "yolo-knn-stage3-demo",
            "model_version": "0.3.0",
            "inference_source": "demo-pipeline",
            "processed_at": datetime.now(UTC).isoformat(),
            "behavior_events": [
                {
                    "device_code": payload["device_code"],
                    "event_time": payload["occurred_at"],
                    "behavior_type": "feeding",
                    "cow_count": 4,
                    "confidence": 0.9,
                    "zone_name": "Water Zone",
                    "notes": None,
                }
            ],
            "raw_metadata": {"pipeline_mode": "demo"},
        }

    monkeypatch.setattr(
        "app.modules.events.router.invoke_inference_service",
        fake_inference_service,
    )
    monkeypatch.setattr(
        "app.modules.media.router.fetch_inference_preview",
        lambda _query: (b"preview", "image/jpeg", None),
    )
    monkeypatch.setattr(
        "app.modules.media.router.fetch_inference_media",
        lambda _query: (b"image-bytes", "image/jpeg", 'inline; filename="frame.jpg"'),
    )

    token = login(client, "admin", "admin123")
    import_response = client.post(
        "/api/v1/events/import",
        json={
            "device_code": "CAM-TEST-001",
            "source_type": "image",
            "source_uri": "/workspace/tests/sample.jpg",
            "occurred_at": datetime.now(UTC).isoformat(),
            "metadata": {},
        },
        headers=auth_headers(token),
    )
    assert import_response.status_code == 200
    event_id = import_response.json()["data"]["behavior_events"][0]["id"]

    preview_response = client.get(
        "/api/v1/media/devices/1/preview",
        headers=auth_headers(token),
    )
    assert preview_response.status_code == 200
    assert preview_response.content == b"preview"

    source_response = client.get(
        f"/api/v1/media/events/{event_id}/source",
        headers=auth_headers(token),
    )
    assert source_response.status_code == 200
    assert source_response.content == b"image-bytes"
