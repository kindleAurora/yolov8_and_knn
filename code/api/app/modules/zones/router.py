from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.audit import record_audit_log
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.models import Device, User, Zone

router = APIRouter(prefix="/zones", tags=["区域管理"])


class ZonePoint(BaseModel):
    x: float
    y: float


class ZoneBase(BaseModel):
    device_id: int
    name: str = Field(min_length=2, max_length=120)
    zone_type: str = Field(min_length=2, max_length=32)
    shape_type: str = Field(default="polygon", min_length=2, max_length=32)
    points: list[ZonePoint]
    is_enabled: bool = True

    @field_validator("points")
    @classmethod
    def validate_points(cls, value: list[ZonePoint]) -> list[ZonePoint]:
        if len(value) < 3:
            raise ValueError("区域至少需要三个坐标点")
        return value


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(ZoneBase):
    pass


class ZoneSummary(BaseModel):
    id: int
    farm_id: int
    device_id: int
    name: str
    zone_type: str
    shape_type: str
    points: list[ZonePoint]
    is_enabled: bool
    updated_at: datetime


def _zone_query():
    return select(Zone).options(selectinload(Zone.device))


def _serialize_zone(zone: Zone) -> ZoneSummary:
    return ZoneSummary(
        id=zone.id,
        farm_id=zone.farm_id,
        device_id=zone.device_id,
        name=zone.name,
        zone_type=zone.zone_type,
        shape_type=zone.shape_type,
        points=[ZonePoint.model_validate(point) for point in zone.points],
        is_enabled=zone.is_enabled,
        updated_at=zone.updated_at,
    )


def _get_device_or_404(db: Session, *, device_id: int, farm_id: int) -> Device:
    device = db.scalar(select(Device).where(Device.id == device_id, Device.farm_id == farm_id))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到设备")
    return device


def _get_zone_or_404(db: Session, *, zone_id: int, farm_id: int) -> Zone:
    zone = db.scalar(_zone_query().where(Zone.id == zone_id, Zone.farm_id == farm_id))
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到区域")
    return zone


@router.get("")
def list_zones(
    device_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    statement = _zone_query().where(Zone.farm_id == current_user.farm_id).order_by(Zone.id.desc())
    if device_id is not None:
        statement = statement.where(Zone.device_id == device_id)
    zones = db.scalars(statement).all()
    return success_response([_serialize_zone(zone).model_dump() for zone in zones])


@router.post("")
def create_zone(
    payload: ZoneCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _get_device_or_404(db, device_id=payload.device_id, farm_id=current_user.farm_id)

    zone = Zone(
        farm_id=current_user.farm_id,
        device_id=payload.device_id,
        name=payload.name,
        zone_type=payload.zone_type,
        shape_type=payload.shape_type,
        points=[point.model_dump() for point in payload.points],
        is_enabled=payload.is_enabled,
    )
    db.add(zone)
    db.flush()
    record_audit_log(
        db,
        action="zone.create",
        target_type="zone",
        target_id=str(zone.id),
        user=current_user,
        detail={"device_id": zone.device_id, "name": zone.name},
        request=request,
    )
    db.commit()
    db.refresh(zone)
    return success_response(_serialize_zone(zone).model_dump(), message="区域创建成功")


@router.put("/{zone_id}")
def update_zone(
    zone_id: int,
    payload: ZoneUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    zone = _get_zone_or_404(db, zone_id=zone_id, farm_id=current_user.farm_id)
    _get_device_or_404(db, device_id=payload.device_id, farm_id=current_user.farm_id)

    zone.device_id = payload.device_id
    zone.name = payload.name
    zone.zone_type = payload.zone_type
    zone.shape_type = payload.shape_type
    zone.points = [point.model_dump() for point in payload.points]
    zone.is_enabled = payload.is_enabled

    record_audit_log(
        db,
        action="zone.update",
        target_type="zone",
        target_id=str(zone.id),
        user=current_user,
        detail={"device_id": zone.device_id, "name": zone.name},
        request=request,
    )
    db.commit()
    db.refresh(zone)
    return success_response(_serialize_zone(zone).model_dump(), message="区域更新成功")


@router.delete("/{zone_id}")
def delete_zone(
    zone_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    zone = _get_zone_or_404(db, zone_id=zone_id, farm_id=current_user.farm_id)

    record_audit_log(
        db,
        action="zone.delete",
        target_type="zone",
        target_id=str(zone.id),
        user=current_user,
        detail={"device_id": zone.device_id, "name": zone.name},
        request=request,
    )
    db.delete(zone)
    db.commit()
    return success_response({"deleted": True}, message="区域删除成功")
