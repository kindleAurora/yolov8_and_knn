from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.event_preview_cache import (
    PREVIEW_CACHE_KEY,
    build_event_preview_cache_path,
    resolve_event_preview_cache_path,
    write_event_preview_cache,
)
from app.core.inference_client import fetch_inference_media, fetch_inference_preview
from app.core.media_sources import resolve_inference_media_uri
from app.core.models import BehaviorEvent, Device, User

router = APIRouter(prefix="/media", tags=["媒体预览"])

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
VIDEO_SUFFIXES = (".mp4", ".avi", ".mov", ".mkv", ".wmv")


def _get_device_or_404(db: Session, *, device_id: int, farm_id: int) -> Device:
    device = db.scalar(select(Device).where(Device.id == device_id, Device.farm_id == farm_id))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到设备")
    return device


def _get_event_or_404(db: Session, *, event_id: int, farm_id: int) -> BehaviorEvent:
    event = db.scalar(
        select(BehaviorEvent).where(BehaviorEvent.id == event_id, BehaviorEvent.farm_id == farm_id)
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到行为事件")
    return event


def _infer_device_source_type(uri: str) -> str:
    parsed = urlparse(uri)
    lower_path = parsed.path.lower()
    if lower_path.endswith(IMAGE_SUFFIXES):
        return "image"
    if lower_path.endswith(VIDEO_SUFFIXES):
        return "video"
    if parsed.scheme in {"rtsp", "rtmp"}:
        return "stream"
    if parsed.scheme in {"http", "https"} and not lower_path:
        return "stream"
    return "stream"


def _proxy_preview_response(query: dict[str, object]) -> Response:
    try:
        payload, media_type, _content_disposition = fetch_inference_preview(query)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return Response(
        content=payload,
        media_type=media_type or "image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


def _proxy_media_response(query: dict[str, object]) -> Response:
    try:
        payload, media_type, content_disposition = fetch_inference_media(query)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    headers = {"Cache-Control": "no-store"}
    if content_disposition:
        headers["Content-Disposition"] = content_disposition

    return Response(
        content=payload,
        media_type=media_type or "application/octet-stream",
        headers=headers,
    )


def _read_numeric_metadata(raw_metadata: dict[str, object], key: str) -> float | None:
    raw_value = raw_metadata.get(key)
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    return None


@router.get("/devices/{device_id}/preview")
def get_device_preview(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    device = _get_device_or_404(db, device_id=device_id, farm_id=current_user.farm_id)
    return _proxy_preview_response(
        {
            "source_type": _infer_device_source_type(device.stream_url),
            "source_uri": resolve_inference_media_uri(device.stream_url),
        }
    )


@router.get("/events/{event_id}/preview")
def get_event_preview(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    event = _get_event_or_404(db, event_id=event_id, farm_id=current_user.farm_id)
    raw_metadata = event.raw_metadata if isinstance(event.raw_metadata, dict) else {}
    cached_preview_path = resolve_event_preview_cache_path(raw_metadata)
    if cached_preview_path is None:
        warmed_preview_path = build_event_preview_cache_path(event.request_id)
        if warmed_preview_path.exists():
            cached_preview_path = warmed_preview_path
    if cached_preview_path is not None:
        return Response(
            content=cached_preview_path.read_bytes(),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    yolo_model_key = raw_metadata.get("yolo_model_key")
    inference_mode = raw_metadata.get("inference_mode")
    query = {
        "source_type": event.source_type,
        "source_uri": resolve_inference_media_uri(event.source_uri),
        "frame_uri": resolve_inference_media_uri(event.frame_uri),
        "prefer_frame": True,
        "annotated": True,
        "inference_mode": inference_mode if isinstance(inference_mode, str) else "yolo-only",
        "yolo_model_key": yolo_model_key if isinstance(yolo_model_key, str) else None,
        "yolo_confidence": _read_numeric_metadata(raw_metadata, "yolo_confidence"),
        "yolo_iou": _read_numeric_metadata(raw_metadata, "yolo_iou"),
        "knn_confidence_threshold": _read_numeric_metadata(raw_metadata, "knn_confidence_threshold"),
    }

    try:
        payload, media_type, _content_disposition = fetch_inference_preview(query)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    try:
        if cached_preview_path is None:
            preview_cache_path = write_event_preview_cache(event.request_id, payload)
            raw_metadata[PREVIEW_CACHE_KEY] = preview_cache_path
            event.raw_metadata = raw_metadata
            db.add(event)
            db.commit()
    except OSError:
        pass

    return Response(
        content=payload,
        media_type=media_type or "image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/events/{event_id}/source")
def get_event_source_media(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    event = _get_event_or_404(db, event_id=event_id, farm_id=current_user.farm_id)
    return _proxy_media_response(
        {
            "source_type": event.source_type,
            "source_uri": event.source_uri,
        }
    )
