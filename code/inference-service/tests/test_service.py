from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.pipelines.runtime import (
    _append_track_observation,
    _build_behavior_events,
    _canonical_behavior_key,
    _extract_zone_candidates,
    _match_detection_zone,
)
from app.schemas.inference import BehaviorEventCandidate, InferenceResponse
from app.schemas.inference import InferenceRequest

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


def test_zone_matching_supports_near_hits() -> None:
    payload = InferenceRequest(
        request_id="req-zone-near",
        source_type="video",
        source_uri="demo.mp4",
        occurred_at=datetime.now(UTC),
        metadata={
            "zone_candidates": [
                {
                    "name": "Feed Zone",
                    "zone_type": "feeding",
                    "shape_type": "polygon",
                    "points": [
                        {"x": 0.4, "y": 0.6},
                        {"x": 0.7, "y": 0.6},
                        {"x": 0.7, "y": 0.9},
                        {"x": 0.4, "y": 0.9},
                    ],
                }
            ]
        },
    )

    zone_candidates = _extract_zone_candidates(payload)
    zone_match = _match_detection_zone(
        zone_candidates,
        x1=40,
        y1=20,
        x2=60,
        y2=58,
        frame_width=100,
        frame_height=100,
    )

    assert zone_match is not None
    assert zone_match.name == "Feed Zone"
    assert zone_match.zone_type == "feeding"
    assert zone_match.relation == "near"


def test_zone_dwell_refines_behavior_events() -> None:
    payload = InferenceRequest(
        request_id="req-zone-rule",
        source_type="video",
        source_uri="demo.mp4",
        occurred_at=datetime.now(UTC),
        device_code="cam-001",
        metadata={
            "zone_candidates": [
                {
                    "name": "Feed Zone",
                    "zone_type": "feeding",
                    "shape_type": "polygon",
                    "points": [
                        {"x": 0.35, "y": 0.55},
                        {"x": 0.75, "y": 0.55},
                        {"x": 0.75, "y": 0.95},
                        {"x": 0.35, "y": 0.95},
                    ],
                }
            ]
        },
    )
    track_observations = {}

    for index in range(4):
        _append_track_observation(
            track_observations,
            track_id="track-1",
            label="standing",
            confidence=0.92,
            offset_seconds=float(index * 3),
            zone_name="Feed Zone",
            zone_type="feeding",
            zone_relation="near",
            observation_span_seconds=3.0,
        )

    behavior_events = _build_behavior_events(payload, track_observations, notes="runtime-test")

    assert len(behavior_events) == 1
    assert _canonical_behavior_key(behavior_events[0].behavior_type) == "feeding"
    assert behavior_events[0].zone_name == "Feed Zone"
    assert behavior_events[0].notes is not None
    assert "zone-rule:feeding" in behavior_events[0].notes
