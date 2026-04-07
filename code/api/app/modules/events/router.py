from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.audit import record_audit_log
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.inference_client import fetch_inference_service_meta, invoke_inference_service
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


class BehaviorEventStats(BaseModel):
    total_count: int
    today_count: int
    recent_events: list[BehaviorEventSummary]


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
    metadata.setdefault(
        "zone_candidates",
        [
            {"name": zone.name, "zone_type": zone.zone_type}
            for zone in unique_zones.values()
        ],
    )
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


def _start_of_today_in_utc(user: User) -> datetime:
    timezone_name = user.farm.timezone if user.farm else "Asia/Shanghai"
    try:
        farm_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        farm_timezone = timezone.utc

    current_time = datetime.now(farm_timezone)
    return current_time.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _resolve_inference_timeout(source_type: str) -> int:
    if source_type == "video":
        return 600
    if source_type == "stream":
        return 180
    return 30


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    total_count = db.scalar(
        select(func.count(BehaviorEvent.id)).where(BehaviorEvent.farm_id == current_user.farm_id)
    ) or 0
    today_count = db.scalar(
        select(func.count(BehaviorEvent.id)).where(
            BehaviorEvent.farm_id == current_user.farm_id,
            BehaviorEvent.occurred_at >= _start_of_today_in_utc(current_user),
        )
    ) or 0
    recent_events = db.scalars(
        _event_query()
        .where(BehaviorEvent.farm_id == current_user.farm_id)
        .order_by(BehaviorEvent.occurred_at.desc(), BehaviorEvent.id.desc())
        .limit(5)
    ).all()

    payload = BehaviorEventStats(
        total_count=total_count,
        today_count=today_count,
        recent_events=[_serialize_event(event) for event in recent_events],
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    device = _get_device_or_404(db, device_code=payload.device_code, farm_id=current_user.farm_id)
    zone_map = _resolve_zone_map(db, farm_id=current_user.farm_id, device_id=device.id)
    request_id = payload.request_id or f"req-{uuid4().hex[:12]}"

    inference_payload = {
        "request_id": request_id,
        "source_type": payload.source_type,
        "source_uri": payload.source_uri,
        "occurred_at": payload.occurred_at.isoformat(),
        "device_code": device.code,
        "frame_uri": payload.frame_uri,
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

    media_asset = _create_media_asset(
        db,
        payload=payload,
        device=device,
        raw_metadata=inference_result.raw_metadata,
    )

    created_event_ids: list[int] = []
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
            raw_metadata=inference_result.raw_metadata,
        )
        db.add(behavior_event)
        db.flush()
        created_event_ids.append(behavior_event.id)

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
