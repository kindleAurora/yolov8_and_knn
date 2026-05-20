from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.audit import record_audit_log
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.models import Device, User

router = APIRouter(prefix="/devices", tags=["设备管理"])


class DeviceBase(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    device_type: str = Field(default="camera", min_length=2, max_length=32)
    stream_url: str = Field(min_length=4)
    install_location: str | None = Field(default=None, max_length=255)
    status: str = Field(default="offline", min_length=2, max_length=32)
    is_enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(DeviceBase):
    pass


class DeviceStatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=32)
    is_enabled: bool


class DeviceSummary(BaseModel):
    id: int
    farm_id: int
    code: str
    name: str
    device_type: str
    stream_url: str
    install_location: str | None
    status: str
    is_enabled: bool
    last_seen_at: datetime | None
    config: dict[str, Any]
    zone_count: int
    updated_at: datetime


def _device_query():
    return select(Device).options(selectinload(Device.zones))


def _serialize_device(device: Device) -> DeviceSummary:
    return DeviceSummary(
        id=device.id,
        farm_id=device.farm_id,
        code=device.code,
        name=device.name,
        device_type=device.device_type,
        stream_url=device.stream_url,
        install_location=device.install_location,
        status=device.status,
        is_enabled=device.is_enabled,
        last_seen_at=device.last_seen_at,
        config=device.config or {},
        zone_count=len(device.zones),
        updated_at=device.updated_at,
    )


def _get_device_or_404(db: Session, *, device_id: int, farm_id: int) -> Device:
    device = db.scalar(_device_query().where(Device.id == device_id, Device.farm_id == farm_id))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到设备")
    return device


def _ensure_unique_code(
    db: Session,
    *,
    code: str,
    farm_id: int,
    excluded_id: int | None = None,
) -> None:
    existing = db.scalar(select(Device.id).where(Device.code == code, Device.farm_id == farm_id))
    if existing is not None and existing != excluded_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="设备编号已存在",
        )


@router.get("")
def list_devices(
    include_disabled: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    statement = (
        _device_query()
        .where(Device.farm_id == current_user.farm_id)
        .order_by(Device.id.desc())
    )
    if not include_disabled:
        statement = statement.where(Device.is_enabled.is_(True))
    devices = db.scalars(statement).all()
    return success_response([_serialize_device(device).model_dump() for device in devices])


@router.get("/{device_id}")
def get_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    device = _get_device_or_404(db, device_id=device_id, farm_id=current_user.farm_id)
    return success_response(_serialize_device(device).model_dump())


@router.post("")
def create_device(
    payload: DeviceCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _ensure_unique_code(db, code=payload.code, farm_id=current_user.farm_id)

    device = Device(farm_id=current_user.farm_id, **payload.model_dump())
    db.add(device)
    db.flush()
    record_audit_log(
        db,
        action="device.create",
        target_type="device",
        target_id=str(device.id),
        user=current_user,
        detail={"code": device.code, "name": device.name},
        request=request,
    )
    db.commit()
    db.refresh(device)
    return success_response(_serialize_device(device).model_dump(), message="设备创建成功")


@router.put("/{device_id}")
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    device = _get_device_or_404(db, device_id=device_id, farm_id=current_user.farm_id)
    _ensure_unique_code(db, code=payload.code, farm_id=current_user.farm_id, excluded_id=device.id)

    for field, value in payload.model_dump().items():
        setattr(device, field, value)

    record_audit_log(
        db,
        action="device.update",
        target_type="device",
        target_id=str(device.id),
        user=current_user,
        detail={"code": device.code, "status": device.status, "enabled": device.is_enabled},
        request=request,
    )
    db.commit()
    db.refresh(device)
    return success_response(_serialize_device(device).model_dump(), message="设备更新成功")


@router.patch("/{device_id}/status")
def update_device_status(
    device_id: int,
    payload: DeviceStatusUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    device = _get_device_or_404(db, device_id=device_id, farm_id=current_user.farm_id)
    device.status = payload.status
    device.is_enabled = payload.is_enabled

    record_audit_log(
        db,
        action="device.status_update",
        target_type="device",
        target_id=str(device.id),
        user=current_user,
        detail=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(device)
    return success_response(_serialize_device(device).model_dump(), message="设备状态更新成功")


@router.delete("/{device_id}")
def delete_device(
    device_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    device = _get_device_or_404(db, device_id=device_id, farm_id=current_user.farm_id)

    record_audit_log(
        db,
        action="device.delete",
        target_type="device",
        target_id=str(device.id),
        user=current_user,
        detail={"code": device.code},
        request=request,
    )
    db.delete(device)
    db.commit()
    return success_response({"deleted": True}, message="设备删除成功")
