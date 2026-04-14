from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.models import Alert, BehaviorEvent, User
from app.modules.alerts.service import ensure_utc_datetime, get_farm_timezone

router = APIRouter(prefix="/history", tags=["历史分析"])


class HistoryBehaviorEventItem(BaseModel):
    id: int
    device_id: int | None
    device_name: str | None
    device_code: str
    zone_name: str | None
    behavior_type: str
    cow_count: int
    confidence: float
    occurred_at: datetime
    source_type: str
    model_name: str


class HistoryAlertItem(BaseModel):
    id: int
    rule_id: int | None
    rule_name: str | None
    device_id: int | None
    device_name: str | None
    device_code: str
    severity: str
    status: str
    title: str
    rule_source: str
    triggered_at: datetime
    handling_note: str | None


class PagedHistoryBehaviorEventResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[HistoryBehaviorEventItem]


class PagedHistoryAlertResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[HistoryAlertItem]


class HistoryTrendPoint(BaseModel):
    label: str
    value: int


class HistorySharePoint(BaseModel):
    label: str
    value: int
    share: float


class HistoryAnalysisSummary(BaseModel):
    window_start: datetime
    window_end: datetime
    total_behavior_events: int
    total_alerts: int
    behavior_trend: list[HistoryTrendPoint]
    alert_trend: list[HistoryTrendPoint]
    behavior_share: list[HistorySharePoint]
    alert_severity_distribution: list[HistorySharePoint]


def _behavior_query():
    return select(BehaviorEvent).options(selectinload(BehaviorEvent.device))


def _alert_query():
    return select(Alert).options(selectinload(Alert.device), selectinload(Alert.rule))


def _serialize_behavior_event(event: BehaviorEvent) -> HistoryBehaviorEventItem:
    return HistoryBehaviorEventItem(
        id=event.id,
        device_id=event.device_id,
        device_name=event.device.name if event.device else None,
        device_code=event.device_code,
        zone_name=event.zone_name,
        behavior_type=event.behavior_type,
        cow_count=event.cow_count,
        confidence=event.confidence,
        occurred_at=event.occurred_at,
        source_type=event.source_type,
        model_name=event.model_name,
    )


def _serialize_alert(alert: Alert) -> HistoryAlertItem:
    return HistoryAlertItem(
        id=alert.id,
        rule_id=alert.rule_id,
        rule_name=alert.rule.name if alert.rule else None,
        device_id=alert.device_id,
        device_name=alert.device.name if alert.device else None,
        device_code=alert.device_code,
        severity=alert.severity,
        status=alert.status,
        title=alert.title,
        rule_source=alert.rule_source,
        triggered_at=alert.triggered_at,
        handling_note=alert.handling_note,
    )


def _resolve_window(
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    current_user: User,
) -> tuple[datetime, datetime]:
    farm_timezone = get_farm_timezone(current_user)
    now_local = datetime.now(farm_timezone)
    resolved_end = ensure_utc_datetime(end_at) if end_at else now_local.astimezone(timezone.utc)
    resolved_start = ensure_utc_datetime(start_at) if start_at else (now_local - timedelta(days=6)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)
    return resolved_start, resolved_end


def _build_label(value: datetime, user: User) -> str:
    return ensure_utc_datetime(value).astimezone(get_farm_timezone(user)).strftime("%m-%d")


def _to_share_points(counter: Counter[str]) -> list[HistorySharePoint]:
    total = sum(counter.values())
    result = [
        HistorySharePoint(label=label, value=value, share=(value / total) if total else 0)
        for label, value in counter.items()
    ]
    result.sort(key=lambda item: (-item.value, item.label))
    return result


@router.get("/behavior-events")
def list_history_behavior_events(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    device_id: int | None = Query(default=None),
    behavior_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    window_start, window_end = _resolve_window(start_at=start_at, end_at=end_at, current_user=current_user)
    filters = [
        BehaviorEvent.farm_id == current_user.farm_id,
        BehaviorEvent.occurred_at >= window_start,
        BehaviorEvent.occurred_at <= window_end,
    ]
    if device_id is not None:
        filters.append(BehaviorEvent.device_id == device_id)
    if behavior_type:
        filters.append(BehaviorEvent.behavior_type == behavior_type)

    total = db.scalar(select(func.count(BehaviorEvent.id)).where(*filters)) or 0
    items = db.scalars(
        _behavior_query()
        .where(*filters)
        .order_by(BehaviorEvent.occurred_at.desc(), BehaviorEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    payload = PagedHistoryBehaviorEventResult(
        total=total,
        page=page,
        page_size=page_size,
        items=[_serialize_behavior_event(item) for item in items],
    )
    return success_response(payload.model_dump())


@router.get("/alerts")
def list_history_alerts(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    device_id: int | None = Query(default=None),
    severity: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    rule_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    filters = [Alert.farm_id == current_user.farm_id]
    if start_at is not None:
        filters.append(Alert.triggered_at >= ensure_utc_datetime(start_at))
    if end_at is not None:
        filters.append(Alert.triggered_at <= ensure_utc_datetime(end_at))
    if device_id is not None:
        filters.append(Alert.device_id == device_id)
    if severity:
        filters.append(Alert.severity == severity)
    if status_filter:
        filters.append(Alert.status == status_filter)
    if rule_source:
        filters.append(Alert.rule_source == rule_source)

    total = db.scalar(select(func.count(Alert.id)).where(*filters)) or 0
    items = db.scalars(
        _alert_query()
        .where(*filters)
        .order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    payload = PagedHistoryAlertResult(
        total=total,
        page=page,
        page_size=page_size,
        items=[_serialize_alert(item) for item in items],
    )
    return success_response(payload.model_dump())


@router.get("/analysis")
def get_history_analysis(
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    device_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    window_start, window_end = _resolve_window(start_at=start_at, end_at=end_at, current_user=current_user)
    behavior_filters = [
        BehaviorEvent.farm_id == current_user.farm_id,
        BehaviorEvent.occurred_at >= window_start,
        BehaviorEvent.occurred_at <= window_end,
    ]
    alert_filters = [
        Alert.farm_id == current_user.farm_id,
        Alert.triggered_at >= window_start,
        Alert.triggered_at <= window_end,
    ]
    if device_id is not None:
        behavior_filters.append(BehaviorEvent.device_id == device_id)
        alert_filters.append(Alert.device_id == device_id)

    behavior_events = db.scalars(
        _behavior_query()
        .where(*behavior_filters)
        .order_by(BehaviorEvent.occurred_at.asc(), BehaviorEvent.id.asc())
    ).all()
    alerts = db.scalars(
        _alert_query()
        .where(*alert_filters)
        .order_by(Alert.triggered_at.asc(), Alert.id.asc())
    ).all()

    behavior_trend_counter: defaultdict[str, int] = defaultdict(int)
    alert_trend_counter: defaultdict[str, int] = defaultdict(int)
    behavior_share_counter: Counter[str] = Counter()
    alert_severity_counter: Counter[str] = Counter()

    for event in behavior_events:
        label = _build_label(event.occurred_at, current_user)
        behavior_trend_counter[label] += 1
        behavior_share_counter[event.behavior_type] += 1

    for alert in alerts:
        label = _build_label(alert.triggered_at, current_user)
        alert_trend_counter[label] += 1
        alert_severity_counter[alert.severity] += 1

    payload = HistoryAnalysisSummary(
        window_start=window_start,
        window_end=window_end,
        total_behavior_events=len(behavior_events),
        total_alerts=len(alerts),
        behavior_trend=[HistoryTrendPoint(label=label, value=value) for label, value in behavior_trend_counter.items()],
        alert_trend=[HistoryTrendPoint(label=label, value=value) for label, value in alert_trend_counter.items()],
        behavior_share=_to_share_points(behavior_share_counter),
        alert_severity_distribution=_to_share_points(alert_severity_counter),
    )
    return success_response(payload.model_dump())
