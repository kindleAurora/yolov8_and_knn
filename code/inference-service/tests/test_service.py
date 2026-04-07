from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.inference import BehaviorEventCandidate, InferenceResponse

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "cow-monitor-inference"


def test_meta_exposes_model_selection() -> None:
    response = client.get("/api/v1/inference/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "cow-monitor-inference"
    assert "available_inference_modes" in payload
    assert "available_yolo_models" in payload


def test_predict_contract(monkeypatch) -> None:
    def fake_run_inference_request(_payload) -> InferenceResponse:
        return InferenceResponse(
            request_id="req-001",
            service="cow-monitor-inference",
            model_name="cow_120_on_basecommon + KNN",
            model_version="best.pt@test",
            inference_source="real-yolo-knn",
            processed_at=datetime.now(UTC),
            behavior_events=[
                BehaviorEventCandidate(
                    device_code="cam-001",
                    event_time=datetime.now(UTC),
                    behavior_type="站立",
                    cow_count=2,
                    confidence=0.91,
                    zone_name=None,
                    notes="测试事件",
                )
            ],
            raw_metadata={"pipeline_mode": "real"},
        )

    monkeypatch.setattr(
        "app.modules.system.router.run_inference_request",
        fake_run_inference_request,
    )

    response = client.post(
        "/api/v1/inference/predict",
        json={
            "request_id": "req-001",
            "source_type": "video",
            "source_uri": "demo.mp4",
            "occurred_at": datetime.now(UTC).isoformat(),
            "device_code": "cam-001",
            "metadata": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-001"
    assert payload["inference_source"] == "real-yolo-knn"
    assert payload["model_name"] == "cow_120_on_basecommon + KNN"
    assert payload["behavior_events"][0]["device_code"] == "cam-001"
    assert "event_time" in payload["behavior_events"][0]


def test_predict_supports_behavior_overrides() -> None:
    response = client.post(
        "/api/v1/inference/predict",
        json={
            "request_id": "req-002",
            "source_type": "image",
            "source_uri": "demo.jpg",
            "occurred_at": datetime.now(UTC).isoformat(),
            "device_code": "cam-002",
            "metadata": {
                "behavior_overrides": [
                    {
                        "behavior_type": "饮水",
                        "cow_count": 2,
                        "confidence": 0.95,
                        "zone_name": "饮水区",
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["behavior_events"]) == 1
    assert payload["behavior_events"][0]["behavior_type"] == "饮水"
    assert payload["inference_source"] == "manual-overrides"


def test_preview_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.system.router.get_media_preview_bytes",
        lambda **_: b"jpeg-preview",
    )

    response = client.get(
        "/api/v1/inference/preview",
        params={
            "source_type": "stream",
            "source_uri": "rtsp://camera/live",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content == b"jpeg-preview"


def test_raw_media_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.system.router.read_media_payload",
        lambda **_: (b"video-bytes", "video/mp4", "sample.mp4"),
    )

    response = client.get(
        "/api/v1/inference/media",
        params={
            "source_type": "video",
            "source_uri": "/workspace/sample.mp4",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert "sample.mp4" in response.headers["content-disposition"]
    assert response.content == b"video-bytes"
