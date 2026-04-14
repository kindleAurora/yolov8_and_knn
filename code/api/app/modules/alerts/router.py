from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.audit import record_audit_log
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.models import Alert, User
from app.modules.alerts.service import ensure_default_rules

router = APIRouter(prefix="/alerts", tags=["告警中心"])

AlertStatus = Literal["open", "acknowledged", "resolved"]


class AlertStatusUpdate(BaseModel):
    status: AlertStatus
    handling_note: str | None = Field(default=None, max_length=1000)


class AlertSummary(BaseModel):
    id: int
    farm_id: int
    rule_id: int | None
    rule_name: str | None
    behavior_event_id: int | None
    device_id: int | None
    device_name: str | None
    device_code: str
    severity: str
    status: str
    title: str
    description: str
    rule_source: str
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    handling_note: str | None
    handled_by_user_name: str | None
    snapshot: dict[str, Any]
    created_at: datetime


class AlertListResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AlertSummary]


class AlertSummaryStats(BaseModel):
    total_count: int
    open_count: int
    acknowledged_count: int
    resolved_count: int
    high_severity_count: int
    recent_alerts: list[AlertSummary]


def _alert_query():
    return select(Alert).options(
        selectinload(Alert.rule),
        selectinload(Alert.device),
        selectinload(Alert.handled_by_user),
        selectinload(Alert.behavior_event),
    )


def _serialize_alert(alert: Alert) -> AlertSummary:
    return AlertSummary(
        id=alert.id,
        farm_id=alert.farm_id,
        rule_id=alert.rule_id,
        rule_name=alert.rule.name if alert.rule else None,
        behavior_event_id=alert.behavior_event_id,
        device_id=alert.device_id,
        device_name=alert.device.name if alert.device else None,
        device_code=alert.device_code,
        severity=alert.severity,
        status=alert.status,
        title=alert.title,
        description=alert.description,
        rule_source=alert.rule_source,
        triggered_at=alert.triggered_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        handling_note=alert.handling_note,
        handled_by_user_name=alert.handled_by_user.display_name if alert.handled_by_user else None,
        snapshot=alert.snapshot or {},
        created_at=alert.created_at,
    )


def _get_alert_or_404(db: Session, *, alert_id: int, farm_id: int) -> Alert:
    alert = db.scalar(_alert_query().where(Alert.id == alert_id, Alert.farm_id == farm_id))
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到告警")
    return alert


@router.get("")
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    rule_source: str | None = Query(default=None),
    device_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_default_rules(db, farm_id=current_user.farm_id)

    filters = [Alert.farm_id == current_user.farm_id]
    if status_filter:
        filters.append(Alert.status == status_filter)
    if severity:
        filters.append(Alert.severity == severity)
    if rule_source:
        filters.append(Alert.rule_source == rule_source)
    if device_id is not None:
        filters.append(Alert.device_id == device_id)

    total = db.scalar(select(func.count(Alert.id)).where(*filters)) or 0
    items = db.scalars(
        _alert_query()
        .where(*filters)
        .order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    payload = AlertListResult(
        total=total,
        page=page,
        page_size=page_size,
        items=[_serialize_alert(item) for item in items],
    )
    return success_response(payload.model_dump())


@router.get("/summary")
def get_alert_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_default_rules(db, farm_id=current_user.farm_id)
    base_filters = [Alert.farm_id == current_user.farm_id]
    total_count = db.scalar(select(func.count(Alert.id)).where(*base_filters)) or 0
    open_count = db.scalar(select(func.count(Alert.id)).where(*base_filters, Alert.status == "open")) or 0
    acknowledged_count = db.scalar(select(func.count(Alert.id)).where(*base_filters, Alert.status == "acknowledged")) or 0
    resolved_count = db.scalar(select(func.count(Alert.id)).where(*base_filters, Alert.status == "resolved")) or 0
    high_severity_count = db.scalar(select(func.count(Alert.id)).where(*base_filters, Alert.severity == "high")) or 0
    recent_alerts = db.scalars(
        _alert_query()
        .where(*base_filters)
        .order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .limit(5)
    ).all()

    payload = AlertSummaryStats(
        total_count=total_count,
        open_count=open_count,
        acknowledged_count=acknowledged_count,
        resolved_count=resolved_count,
        high_severity_count=high_severity_count,
        recent_alerts=[_serialize_alert(item) for item in recent_alerts],
    )
    return success_response(payload.model_dump())


@router.get("/{alert_id}")
def get_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    alert = _get_alert_or_404(db, alert_id=alert_id, farm_id=current_user.farm_id)
    return success_response(_serialize_alert(alert).model_dump())


@router.patch("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    alert = _get_alert_or_404(db, alert_id=alert_id, farm_id=current_user.farm_id)

    alert.status = payload.status
    alert.handling_note = payload.handling_note
    alert.handled_by_user_id = current_user.id

    current_time = datetime.now(timezone.utc)
    if payload.status == "acknowledged" and alert.acknowledged_at is None:
        alert.acknowledged_at = current_time
    if payload.status == "resolved":
        if alert.acknowledged_at is None:
            alert.acknowledged_at = current_time
        alert.resolved_at = current_time
    if payload.status != "resolved":
        alert.resolved_at = None

    record_audit_log(
        db,
        action="alert.status_update",
        target_type="alert",
        target_id=str(alert.id),
        user=current_user,
        detail={"status": payload.status, "handling_note": payload.handling_note},
        request=request,
    )
    db.commit()
    db.refresh(alert)
    return success_response(_serialize_alert(alert).model_dump(), message="告警状态更新成功")
