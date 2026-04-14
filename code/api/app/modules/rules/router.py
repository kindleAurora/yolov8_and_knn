from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.audit import record_audit_log
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.models import AlertRule, Device, User
from app.modules.alerts.service import ensure_default_rules

router = APIRouter(prefix="/rules", tags=["规则配置"])

RuleType = Literal["lying_duration", "zone_dwell", "no_drinking"]
RuleSeverity = Literal["low", "medium", "high"]


class AlertRuleBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    rule_type: RuleType
    severity: RuleSeverity = "medium"
    threshold_minutes: int = Field(default=30, ge=1, le=24 * 60)
    device_id: int | None = None
    zone_name: str | None = Field(default=None, max_length=120)
    behavior_type: str | None = Field(default=None, max_length=64)
    is_enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(AlertRuleBase):
    pass


class AlertRuleStatusUpdate(BaseModel):
    is_enabled: bool


class AlertRuleSummary(BaseModel):
    id: int
    farm_id: int
    device_id: int | None
    device_name: str | None
    name: str
    description: str | None
    rule_type: str
    severity: str
    source: str
    threshold_minutes: int
    zone_name: str | None
    behavior_type: str | None
    is_enabled: bool
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


def _rule_query():
    return select(AlertRule).options(selectinload(AlertRule.device))


def _serialize_rule(rule: AlertRule) -> AlertRuleSummary:
    return AlertRuleSummary(
        id=rule.id,
        farm_id=rule.farm_id,
        device_id=rule.device_id,
        device_name=rule.device.name if rule.device else None,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        severity=rule.severity,
        source=rule.source,
        threshold_minutes=rule.threshold_minutes,
        zone_name=rule.zone_name,
        behavior_type=rule.behavior_type,
        is_enabled=rule.is_enabled,
        config=rule.config or {},
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _get_rule_or_404(db: Session, *, rule_id: int, farm_id: int) -> AlertRule:
    rule = db.scalar(_rule_query().where(AlertRule.id == rule_id, AlertRule.farm_id == farm_id))
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到规则")
    return rule


def _validate_device(db: Session, *, device_id: int | None, farm_id: int) -> None:
    if device_id is None:
        return
    existing_device = db.scalar(select(Device.id).where(Device.id == device_id, Device.farm_id == farm_id))
    if existing_device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则绑定的设备不存在")


def _normalize_rule_payload(payload: AlertRuleBase, *, source: str) -> dict[str, Any]:
    behavior_type = payload.behavior_type
    zone_name = payload.zone_name.strip() if payload.zone_name else None

    if payload.rule_type == "lying_duration" and not behavior_type:
        behavior_type = "躺卧"
    if payload.rule_type == "no_drinking" and not behavior_type:
        behavior_type = "饮水"

    return {
        "name": payload.name,
        "description": payload.description,
        "rule_type": payload.rule_type,
        "severity": payload.severity,
        "threshold_minutes": payload.threshold_minutes,
        "device_id": payload.device_id,
        "zone_name": zone_name,
        "behavior_type": behavior_type,
        "is_enabled": payload.is_enabled,
        "config": payload.config,
        "source": source,
    }


@router.get("")
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_default_rules(db, farm_id=current_user.farm_id)
    rules = db.scalars(
        _rule_query()
        .where(AlertRule.farm_id == current_user.farm_id)
        .order_by(AlertRule.source.asc(), AlertRule.id.asc())
    ).all()
    return success_response([_serialize_rule(rule).model_dump() for rule in rules])


@router.post("")
def create_rule(
    payload: AlertRuleCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_device(db, device_id=payload.device_id, farm_id=current_user.farm_id)

    rule = AlertRule(
        farm_id=current_user.farm_id,
        **_normalize_rule_payload(payload, source="custom"),
    )
    db.add(rule)
    db.flush()
    record_audit_log(
        db,
        action="rule.create",
        target_type="alert_rule",
        target_id=str(rule.id),
        user=current_user,
        detail={"name": rule.name, "rule_type": rule.rule_type, "source": rule.source},
        request=request,
    )
    db.commit()
    db.refresh(rule)
    return success_response(_serialize_rule(rule).model_dump(), message="规则创建成功")


@router.put("/{rule_id}")
def update_rule(
    rule_id: int,
    payload: AlertRuleUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rule = _get_rule_or_404(db, rule_id=rule_id, farm_id=current_user.farm_id)
    _validate_device(db, device_id=payload.device_id, farm_id=current_user.farm_id)

    for field, value in _normalize_rule_payload(payload, source=rule.source).items():
        setattr(rule, field, value)

    record_audit_log(
        db,
        action="rule.update",
        target_type="alert_rule",
        target_id=str(rule.id),
        user=current_user,
        detail={"name": rule.name, "rule_type": rule.rule_type, "enabled": rule.is_enabled},
        request=request,
    )
    db.commit()
    db.refresh(rule)
    return success_response(_serialize_rule(rule).model_dump(), message="规则更新成功")


@router.patch("/{rule_id}/status")
def update_rule_status(
    rule_id: int,
    payload: AlertRuleStatusUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rule = _get_rule_or_404(db, rule_id=rule_id, farm_id=current_user.farm_id)
    rule.is_enabled = payload.is_enabled
    record_audit_log(
        db,
        action="rule.status_update",
        target_type="alert_rule",
        target_id=str(rule.id),
        user=current_user,
        detail={"is_enabled": payload.is_enabled},
        request=request,
    )
    db.commit()
    db.refresh(rule)
    return success_response(_serialize_rule(rule).model_dump(), message="规则状态更新成功")


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rule = _get_rule_or_404(db, rule_id=rule_id, farm_id=current_user.farm_id)
    if rule.source == "preset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="预设规则不可删除")

    record_audit_log(
        db,
        action="rule.delete",
        target_type="alert_rule",
        target_id=str(rule.id),
        user=current_user,
        detail={"name": rule.name, "rule_type": rule.rule_type},
        request=request,
    )
    db.delete(rule)
    db.commit()
    return success_response({"id": rule_id}, message="规则删除成功")
