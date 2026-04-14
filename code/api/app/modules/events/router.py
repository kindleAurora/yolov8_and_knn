from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.modules.alerts.service import evaluate_alert_rules
from app.core.audit import record_audit_log
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.event_preview_cache import PREVIEW_CACHE_KEY, write_event_preview_cache
from app.core.inference_client import (
    fetch_inference_preview,
    fetch_inference_service_meta,
    invoke_inference_service,
)
from app.core.media_sources import resolve_inference_media_uri
from app.core.models import BehaviorEvent, Device, MediaAsset, User, Zone

router = APIRouter(prefix="/events", tags=["行为事件"])


class InferenceImportRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=64)
    device_code: str = Field(min_length=2, max_length=64)
    source_type: Literal["image", "video", "stream", "edge-report"]
    source_uri: str = Field(min_length=1)
    occurred_at: datetime
    frame_uri: str | None = None
    inference_mode: Literal["yolo-knn", "yolo-only"] = "yolo-knn"
    yolo_model_key: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InferenceBehaviorEvent(BaseModel):
    device_code: str
    event_time: datetime
    behavior_type: str
    cow_count: int
    confidence: float
    zone_name: str | None = None
    notes: str | None = None


class InferenceServiceResponse(BaseModel):
    request_id: str
    service: str
    model_name: str
    model_version: str
    inference_source: str
    processed_at: datetime
    behavior_events: list[InferenceBehaviorEvent]
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class InferenceModelOption(BaseModel):
    key: str
    label: str
    path: str
    is_default: bool = False


class InferenceServiceMeta(BaseModel):
    service: str
    service_mode: str
    supported_sources: list[str]
    available_inference_modes: list[str]
    default_inference_mode: str
    default_yolo_model_key: str | None = None
    default_yolo_confidence: float
    default_yolo_iou: float
    default_knn_confidence_threshold: float
    available_yolo_models: list[InferenceModelOption]
    knn_model_loaded: bool


class BehaviorEventSummary(BaseModel):
    id: int
    request_id: str
    farm_id: int
    device_id: int | None
    device_code: str
    device_name: str | None
    zone_id: int | None
    zone_name: str | None
    behavior_type: str
    cow_count: int
    confidence: float
    occurred_at: datetime
    model_name: str
    model_version: str
    inference_source: str
    source_type: str
    source_uri: str
    frame_uri: str | None
    notes: str | None
    media_asset_id: int | None
    media_asset_uri: str | None
    created_at: datetime


class BehaviorEventImportResult(BaseModel):
    request_id: str
    imported_count: int
    model_name: str
    model_version: str
    inference_source: str
    media_asset_id: int | None
    behavior_events: list[BehaviorEventSummary]


class BehaviorBreakdownItem(BaseModel):
    behavior_key: str
    behavior_type: str
    event_count: int
    cow_count_total: int
    duration_seconds: int
    event_share: float
    duration_share: float


class BehaviorTimelineSegment(BaseModel):
    behavior_key: str
    behavior_type: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: int


class DailyBehaviorOverview(BaseModel):
    date: str
    window_started_at: datetime
    window_ended_at: datetime
    total_events: int
    tracked_duration_seconds: int
    lying_event_count: int
    standing_duration_seconds: int
    dominant_behavior: str | None
    breakdown: list[BehaviorBreakdownItem]
    timeline: list[BehaviorTimelineSegment]


class BehaviorEventStats(BaseModel):
    total_count: int
    today_count: int
    recent_events: list[BehaviorEventSummary]
    today_behavior_overview: DailyBehaviorOverview


CANONICAL_BEHAVIOR_LABELS = {
    "lying": "躺卧",
    "standing": "站立",
    "walking": "行走",
    "feeding": "采食",
    "drinking": "饮水",
    "resting": "休息",
    "other": "其他",
}


def _event_query():
    return select(BehaviorEvent).options(
        selectinload(BehaviorEvent.device),
        selectinload(BehaviorEvent.zone),
        selectinload(BehaviorEvent.media_asset),
    )


def _serialize_event(event: BehaviorEvent) -> BehaviorEventSummary:
    return BehaviorEventSummary(
        id=event.id,
        request_id=event.request_id,
        farm_id=event.farm_id,
        device_id=event.device_id,
        device_code=event.device_code,
        device_name=event.device.name if event.device else None,
        zone_id=event.zone_id,
        zone_name=event.zone_name or (event.zone.name if event.zone else None),
        behavior_type=event.behavior_type,
        cow_count=event.cow_count,
        confidence=event.confidence,
        occurred_at=event.occurred_at,
        model_name=event.model_name,
        model_version=event.model_version,
        inference_source=event.inference_source,
        source_type=event.source_type,
        source_uri=event.source_uri,
        frame_uri=event.frame_uri,
        notes=event.notes,
        media_asset_id=event.media_asset_id,
        media_asset_uri=event.media_asset.uri if event.media_asset else None,
        created_at=event.created_at,
    )


def _get_device_or_404(db: Session, *, device_code: str, farm_id: int) -> Device:
    device = db.scalar(select(Device).where(Device.code == device_code, Device.farm_id == farm_id))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应设备")
    return device


def _get_farm_timezone(user: User) -> ZoneInfo | timezone:
    timezone_name = user.farm.timezone if user.farm else "Asia/Shanghai"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _resolve_zone_map(db: Session, *, farm_id: int, device_id: int) -> dict[str, Zone]:
    zones = db.scalars(
        select(Zone).where(
            Zone.farm_id == farm_id,
            Zone.device_id == device_id,
            Zone.is_enabled.is_(True),
        )
    ).all()

    mapping: dict[str, Zone] = {}
    for zone in zones:
        mapping[zone.name] = zone
        mapping.setdefault(zone.zone_type, zone)
    return mapping


def _build_import_metadata(
    payload: InferenceImportRequest,
    device: Device,
    zone_map: dict[str, Zone],
) -> dict[str, Any]:
    metadata = dict(payload.metadata)
    unique_zones = {zone.id: zone for zone in zone_map.values()}
    metadata["zone_candidates"] = [
        {
            "name": zone.name,
            "zone_type": zone.zone_type,
            "shape_type": zone.shape_type,
            "points": zone.points,
        }
        for zone in unique_zones.values()
    ]
    metadata.setdefault("device_name", device.name)
    if device.install_location:
        metadata.setdefault("install_location", device.install_location)
    return metadata


def _create_media_asset(
    db: Session,
    *,
    payload: InferenceImportRequest,
    device: Device,
    raw_metadata: dict[str, Any],
) -> MediaAsset:
    asset_uri = payload.frame_uri or payload.source_uri
    if payload.frame_uri:
        asset_type = "image"
        role = "frame"
    elif payload.source_type == "video":
        asset_type = "video"
        role = "source"
    elif payload.source_type == "stream":
        asset_type = "stream"
        role = "source"
    elif payload.source_type == "image":
        asset_type = "image"
        role = "source"
    else:
        asset_type = "report"
        role = "source"

    media_asset = MediaAsset(
        farm_id=device.farm_id,
        device_id=device.id,
        device_code=device.code,
        asset_type=asset_type,
        role=role,
        uri=asset_uri,
        captured_at=payload.occurred_at,
        asset_metadata=raw_metadata,
    )
    db.add(media_asset)
    db.flush()
    return media_asset


def _today_window(user: User) -> tuple[datetime, datetime, str]:
    farm_timezone = _get_farm_timezone(user)
    current_time = datetime.now(farm_timezone)
    start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        start_of_day.astimezone(timezone.utc),
        current_time.astimezone(timezone.utc),
        start_of_day.date().isoformat(),
    )


def _resolve_inference_timeout(source_type: str) -> int:
    if source_type == "video":
        return 600
    if source_type == "stream":
        return 180
    return 30


def _build_preview_query(
    *,
    source_type: str,
    source_uri: str,
    frame_uri: str | None,
    inference_mode: str,
    yolo_model_key: str | None,
    yolo_confidence: float | None = None,
    yolo_iou: float | None = None,
    knn_confidence_threshold: float | None = None,
) -> dict[str, object]:
    return {
        "source_type": source_type,
        "source_uri": source_uri,
        "frame_uri": frame_uri,
        "prefer_frame": True,
        "annotated": True,
        "inference_mode": inference_mode,
        "yolo_model_key": yolo_model_key,
        "yolo_confidence": yolo_confidence,
        "yolo_iou": yolo_iou,
        "knn_confidence_threshold": knn_confidence_threshold,
    }


def _generate_preview_cache(
    *,
    request_id: str,
    preview_query: dict[str, object],
) -> str | None:
    try:
        payload, _media_type, _content_disposition = fetch_inference_preview(preview_query)
    except RuntimeError:
        return None
    except OSError:
        return None


def _read_numeric_metadata(metadata: dict[str, Any], key: str) -> float | None:
    raw_value = metadata.get(key)
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    return None

    try:
        return write_event_preview_cache(request_id, payload)
    except OSError:
        return None


def _normalize_behavior_value(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ")


def _ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_behavior_key(raw_value: str) -> str:
    normalized = _normalize_behavior_value(raw_value)

    if normalized in {"lying", "lie", "lay down"}:
        return "lying"
    if normalized in {"standing", "stand"}:
        return "standing"
    if normalized in {"walking", "walk", "moving"}:
        return "walking"
    if normalized in {"feeding", "feed", "eating", "eat"}:
        return "feeding"
    if normalized in {"drinking", "drink"}:
        return "drinking"
    if normalized in {"resting", "rest"}:
        return "resting"

    if "躺" in raw_value or "卧" in raw_value or "lying" in normalized:
        return "lying"
    if "站" in raw_value or "standing" in normalized:
        return "standing"
    if "走" in raw_value or "walking" in normalized:
        return "walking"
    if "采食" in raw_value or "进食" in raw_value or "feeding" in normalized or "eat" in normalized:
        return "feeding"
    if "饮水" in raw_value or "喝水" in raw_value or "drinking" in normalized:
        return "drinking"
    if "休息" in raw_value or "rest" in normalized:
        return "resting"
    return "other"


def _display_behavior_label(raw_value: str, behavior_key: str) -> str:
    return CANONICAL_BEHAVIOR_LABELS.get(behavior_key, raw_value.strip() or "其他")


def _build_daily_behavior_overview(
    events: list[BehaviorEvent],
    *,
    window_started_at: datetime,
    window_ended_at: datetime,
    date_label: str,
) -> DailyBehaviorOverview:
    normalized_window_started_at = _ensure_utc_datetime(window_started_at)
    normalized_window_ended_at = _ensure_utc_datetime(window_ended_at)
    ordered_events = sorted(
        events,
        key=lambda item: (_ensure_utc_datetime(item.occurred_at), item.id),
    )
    aggregates: dict[str, dict[str, int | str]] = {}
    timeline: list[BehaviorTimelineSegment] = []

    for index, event in enumerate(ordered_events):
        event_occurred_at = _ensure_utc_datetime(event.occurred_at)
        behavior_key = _canonical_behavior_key(event.behavior_type)
        behavior_label = _display_behavior_label(event.behavior_type, behavior_key)
        bucket = aggregates.setdefault(
            behavior_key,
            {
                "behavior_type": behavior_label,
                "event_count": 0,
                "cow_count_total": 0,
                "duration_seconds": 0,
            },
        )
        bucket["event_count"] = int(bucket["event_count"]) + 1
        bucket["cow_count_total"] = int(bucket["cow_count_total"]) + max(event.cow_count, 0)

        next_time = normalized_window_ended_at
        if index + 1 < len(ordered_events):
            next_time = min(
                _ensure_utc_datetime(ordered_events[index + 1].occurred_at),
                normalized_window_ended_at,
            )
        duration_seconds = max(0, int((next_time - event_occurred_at).total_seconds()))
        bucket["duration_seconds"] = int(bucket["duration_seconds"]) + duration_seconds

        if duration_seconds == 0:
            continue

        segment_start = max(event_occurred_at, normalized_window_started_at)
        segment_end = next_time
        if segment_end <= segment_start:
            continue

        if timeline and timeline[-1].behavior_key == behavior_key and timeline[-1].ended_at == segment_start:
            previous_segment = timeline[-1]
            timeline[-1] = BehaviorTimelineSegment(
                behavior_key=previous_segment.behavior_key,
                behavior_type=previous_segment.behavior_type,
                started_at=previous_segment.started_at,
                ended_at=segment_end,
                duration_seconds=int((segment_end - previous_segment.started_at).total_seconds()),
            )
            continue

        timeline.append(
            BehaviorTimelineSegment(
                behavior_key=behavior_key,
                behavior_type=behavior_label,
                started_at=segment_start,
                ended_at=segment_end,
                duration_seconds=int((segment_end - segment_start).total_seconds()),
            )
        )

    total_events = len(ordered_events)
    tracked_duration_seconds = sum(segment.duration_seconds for segment in timeline)

    breakdown = [
        BehaviorBreakdownItem(
            behavior_key=behavior_key,
            behavior_type=str(item["behavior_type"]),
            event_count=int(item["event_count"]),
            cow_count_total=int(item["cow_count_total"]),
            duration_seconds=int(item["duration_seconds"]),
            event_share=(int(item["event_count"]) / total_events) if total_events else 0,
            duration_share=(int(item["duration_seconds"]) / tracked_duration_seconds) if tracked_duration_seconds else 0,
        )
        for behavior_key, item in aggregates.items()
    ]
    breakdown.sort(key=lambda item: (-item.duration_seconds, -item.event_count, item.behavior_type))

    dominant_behavior = breakdown[0].behavior_type if breakdown else None
    lying_bucket = next((item for item in breakdown if item.behavior_key == "lying"), None)
    standing_bucket = next((item for item in breakdown if item.behavior_key == "standing"), None)

    return DailyBehaviorOverview(
        date=date_label,
        window_started_at=normalized_window_started_at,
        window_ended_at=normalized_window_ended_at,
        total_events=total_events,
        tracked_duration_seconds=tracked_duration_seconds,
        lying_event_count=lying_bucket.event_count if lying_bucket else 0,
        standing_duration_seconds=standing_bucket.duration_seconds if standing_bucket else 0,
        dominant_behavior=dominant_behavior,
        breakdown=breakdown,
        timeline=timeline,
    )


@router.get("")
def list_behavior_events(
    device_id: int | None = Query(default=None),
    behavior_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    statement = _event_query().where(BehaviorEvent.farm_id == current_user.farm_id)
    if device_id is not None:
        statement = statement.where(BehaviorEvent.device_id == device_id)
    if behavior_type:
        statement = statement.where(BehaviorEvent.behavior_type == behavior_type)
    statement = statement.order_by(
        BehaviorEvent.occurred_at.desc(),
        BehaviorEvent.id.desc(),
    ).limit(limit)

    events = db.scalars(statement).all()
    return success_response([_serialize_event(event).model_dump() for event in events])


@router.get("/summary")
def get_behavior_event_summary(
    device_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    base_filters = [BehaviorEvent.farm_id == current_user.farm_id]
    if device_id is not None:
        base_filters.append(BehaviorEvent.device_id == device_id)

    today_started_at, today_ended_at, date_label = _today_window(current_user)
    total_count = db.scalar(
        select(func.count(BehaviorEvent.id)).where(*base_filters)
    ) or 0
    today_count = db.scalar(
        select(func.count(BehaviorEvent.id)).where(
            *base_filters,
            BehaviorEvent.occurred_at >= today_started_at,
            BehaviorEvent.occurred_at < today_ended_at,
        )
    ) or 0
    recent_events = db.scalars(
        _event_query()
        .where(*base_filters)
        .order_by(BehaviorEvent.occurred_at.desc(), BehaviorEvent.id.desc())
        .limit(5)
    ).all()
    today_events = db.scalars(
        _event_query()
        .where(
            *base_filters,
            BehaviorEvent.occurred_at >= today_started_at,
            BehaviorEvent.occurred_at < today_ended_at,
        )
        .order_by(BehaviorEvent.occurred_at.asc(), BehaviorEvent.id.asc())
    ).all()

    payload = BehaviorEventStats(
        total_count=total_count,
        today_count=today_count,
        recent_events=[_serialize_event(event) for event in recent_events],
        today_behavior_overview=_build_daily_behavior_overview(
            today_events,
            window_started_at=today_started_at,
            window_ended_at=today_ended_at,
            date_label=date_label,
        ),
    )
    return success_response(payload.model_dump())


@router.get("/inference-meta")
def get_inference_meta(
    _current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    try:
        payload = InferenceServiceMeta.model_validate(fetch_inference_service_meta())
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return success_response(payload.model_dump())


@router.post("/import")
def import_behavior_events(
    payload: InferenceImportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    device = _get_device_or_404(db, device_code=payload.device_code, farm_id=current_user.farm_id)
    zone_map = _resolve_zone_map(db, farm_id=current_user.farm_id, device_id=device.id)
    request_id = payload.request_id or f"req-{uuid4().hex[:12]}"
    resolved_source_uri = resolve_inference_media_uri(payload.source_uri)
    resolved_frame_uri = resolve_inference_media_uri(payload.frame_uri)

    inference_payload = {
        "request_id": request_id,
        "source_type": payload.source_type,
        "source_uri": resolved_source_uri,
        "occurred_at": payload.occurred_at.isoformat(),
        "device_code": device.code,
        "frame_uri": resolved_frame_uri,
        "inference_mode": payload.inference_mode,
        "yolo_model_key": payload.yolo_model_key,
        "metadata": _build_import_metadata(payload, device, zone_map),
    }

    try:
        inference_result = InferenceServiceResponse.model_validate(
            invoke_inference_service(
                inference_payload,
                timeout=_resolve_inference_timeout(payload.source_type),
            )
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    event_raw_metadata = dict(inference_result.raw_metadata)
    preview_cache_path = None
    preview_query = _build_preview_query(
        source_type=payload.source_type,
        source_uri=resolved_source_uri,
        frame_uri=resolved_frame_uri,
        inference_mode=payload.inference_mode,
        yolo_model_key=(
            event_raw_metadata.get("yolo_model_key")
            if isinstance(event_raw_metadata.get("yolo_model_key"), str)
            else payload.yolo_model_key
        ),
        yolo_confidence=_read_numeric_metadata(event_raw_metadata, "yolo_confidence"),
        yolo_iou=_read_numeric_metadata(event_raw_metadata, "yolo_iou"),
        knn_confidence_threshold=_read_numeric_metadata(event_raw_metadata, "knn_confidence_threshold"),
    )
    if str(payload.metadata.get("analysis_profile", "")).strip().lower() != "realtime":
        preview_cache_path = _generate_preview_cache(
            request_id=request_id,
            preview_query=preview_query,
        )
    else:
        background_tasks.add_task(
            _generate_preview_cache,
            request_id=request_id,
            preview_query=preview_query,
        )
    if preview_cache_path:
        event_raw_metadata[PREVIEW_CACHE_KEY] = preview_cache_path

    media_asset = _create_media_asset(
        db,
        payload=payload,
        device=device,
        raw_metadata=event_raw_metadata,
    )

    created_event_ids: list[int] = []
    created_events: list[BehaviorEvent] = []
    for event_candidate in inference_result.behavior_events:
        zone = zone_map.get(event_candidate.zone_name) if event_candidate.zone_name else None
        behavior_event = BehaviorEvent(
            farm_id=current_user.farm_id,
            device_id=device.id,
            zone_id=zone.id if zone else None,
            media_asset_id=media_asset.id,
            request_id=request_id,
            device_code=event_candidate.device_code or device.code,
            zone_name=event_candidate.zone_name or (zone.name if zone else None),
            behavior_type=event_candidate.behavior_type,
            occurred_at=event_candidate.event_time,
            cow_count=event_candidate.cow_count,
            confidence=event_candidate.confidence,
            model_name=inference_result.model_name,
            model_version=inference_result.model_version,
            inference_source=inference_result.inference_source,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            frame_uri=payload.frame_uri,
            notes=event_candidate.notes,
            raw_metadata=event_raw_metadata,
        )
        db.add(behavior_event)
        db.flush()
        created_event_ids.append(behavior_event.id)
        created_events.append(behavior_event)

    created_alerts = evaluate_alert_rules(
        db,
        current_user=current_user,
        device=device,
        events=created_events,
    )

    record_audit_log(
        db,
        action="event.import",
        target_type="behavior_event",
        target_id=request_id,
        user=current_user,
        detail={
            "device_code": device.code,
            "source_type": payload.source_type,
            "inference_mode": payload.inference_mode,
            "yolo_model_key": payload.yolo_model_key,
            "imported_count": len(created_event_ids),
            "model_name": inference_result.model_name,
            "model_version": inference_result.model_version,
            "generated_alert_count": len(created_alerts),
        },
        request=request,
    )
    db.commit()

    persisted_events = db.scalars(
        _event_query()
        .where(BehaviorEvent.id.in_(created_event_ids))
        .order_by(BehaviorEvent.occurred_at.desc(), BehaviorEvent.id.desc())
    ).all()

    response_payload = BehaviorEventImportResult(
        request_id=request_id,
        imported_count=len(created_event_ids),
        model_name=inference_result.model_name,
        model_version=inference_result.model_version,
        inference_source=inference_result.inference_source,
        media_asset_id=media_asset.id,
        behavior_events=[_serialize_event(event) for event in persisted_events],
    )
    return success_response(response_payload.model_dump(), message="行为事件导入成功")
