from datetime import UTC, datetime, timedelta
from typing import Any

from app.schemas.inference import BehaviorEventCandidate, InferenceRequest, InferenceResponse

BEHAVIOR_LIBRARY = ["站立", "行走", "采食", "饮水", "休息"]


def _pick_zone_name(metadata: dict[str, Any], index: int) -> str | None:
    zone_candidates = metadata.get("zone_candidates")
    if not isinstance(zone_candidates, list) or len(zone_candidates) == 0:
        return None

    candidate = zone_candidates[index % len(zone_candidates)]
    if not isinstance(candidate, dict):
        return None

    name = candidate.get("name")
    if isinstance(name, str) and name:
        return name

    zone_type = candidate.get("zone_type")
    return zone_type if isinstance(zone_type, str) and zone_type else None


def _build_events_from_overrides(payload: InferenceRequest) -> list[BehaviorEventCandidate]:
    overrides = payload.metadata.get("behavior_overrides")
    if not isinstance(overrides, list):
        return []

    behavior_events: list[BehaviorEventCandidate] = []
    for item in overrides:
        if not isinstance(item, dict):
            continue

        behavior_type = item.get("behavior_type")
        if not isinstance(behavior_type, str) or not behavior_type:
            continue

        offset_seconds = item.get("event_offset_seconds", 0)
        offset_value = offset_seconds if isinstance(offset_seconds, (int, float)) else 0
        event_time = payload.occurred_at + timedelta(seconds=float(offset_value))

        cow_count = item.get("cow_count", 1)
        confidence = item.get("confidence", 0.8)
        zone_name = item.get("zone_name")
        notes = item.get("notes")

        behavior_events.append(
            BehaviorEventCandidate(
                device_code=payload.device_code or "unknown-device",
                event_time=event_time,
                behavior_type=behavior_type,
                cow_count=max(0, int(cow_count)) if isinstance(cow_count, (int, float)) else 0,
                confidence=float(confidence) if isinstance(confidence, (int, float)) else 0.0,
                zone_name=zone_name if isinstance(zone_name, str) else None,
                notes=notes if isinstance(notes, str) else None,
            )
        )

    return behavior_events


def _build_demo_events(payload: InferenceRequest) -> list[BehaviorEventCandidate]:
    source_fingerprint = f"{payload.device_code}|{payload.source_uri}|{payload.source_type}"
    checksum = sum(ord(char) for char in source_fingerprint)
    event_count = 2 if payload.source_type in {"video", "stream"} else 1
    behavior_events: list[BehaviorEventCandidate] = []

    for index in range(event_count):
        behavior_events.append(
            BehaviorEventCandidate(
                device_code=payload.device_code or "unknown-device",
                event_time=payload.occurred_at + timedelta(seconds=index * 15),
                behavior_type=BEHAVIOR_LIBRARY[(checksum + index * 2) % len(BEHAVIOR_LIBRARY)],
                cow_count=max(1, ((checksum // (index + 1)) % 6) + 1),
                confidence=round(0.78 + (((checksum + index * 7) % 17) / 100), 2),
                zone_name=_pick_zone_name(payload.metadata, index),
                notes="阶段 3 演示推理结果，可替换为真实 YOLOv8 + KNN 流程。",
            )
        )

    return behavior_events


def run_stub_inference(payload: InferenceRequest) -> InferenceResponse:
    behavior_events = _build_events_from_overrides(payload) or _build_demo_events(payload)

    return InferenceResponse(
        request_id=payload.request_id,
        service="cow-monitor-inference",
        model_name="yolo-knn-stage3-demo",
        model_version="0.3.0",
        inference_source="demo-pipeline",
        processed_at=datetime.now(UTC),
        behavior_events=behavior_events,
        raw_metadata={
            "source_type": payload.source_type,
            "device_code": payload.device_code,
            "pipeline_mode": "demo",
            "frame_uri": payload.frame_uri,
            "generated_events": len(behavior_events),
            "has_behavior_overrides": bool(_build_events_from_overrides(payload)),
        },
    )
