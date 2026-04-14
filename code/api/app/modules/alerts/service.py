from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.models import Alert, AlertRule, BehaviorEvent, Device, User

DEFAULT_RULE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "持续躺卧超时",
        "description": "检测到牛只持续处于躺卧状态超过阈值后触发告警。",
        "rule_type": "lying_duration",
        "severity": "high",
        "source": "preset",
        "threshold_minutes": 30,
        "behavior_type": "躺卧",
        "config": {"auto_seed": True},
    },
    {
        "name": "区域停留超时",
        "description": "检测到牛只在同一区域停留过久后触发告警。",
        "rule_type": "zone_dwell",
        "severity": "medium",
        "source": "preset",
        "threshold_minutes": 20,
        "config": {"auto_seed": True},
    },
    {
        "name": "长时间未进入饮水区",
        "description": "较长时间没有出现饮水行为时触发提醒。",
        "rule_type": "no_drinking",
        "severity": "medium",
        "source": "preset",
        "threshold_minutes": 120,
        "behavior_type": "饮水",
        "config": {"auto_seed": True},
    },
)

UNRESOLVED_ALERT_STATUSES = ("open", "acknowledged")


def ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_behavior_value(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ")


def canonical_behavior_key(raw_value: str) -> str:
    normalized = normalize_behavior_value(raw_value)

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


def get_farm_timezone(user: User) -> ZoneInfo | timezone:
    timezone_name = user.farm.timezone if user.farm else "Asia/Shanghai"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def start_of_day_in_utc(event_time: datetime, user: User) -> datetime:
    localized = ensure_utc_datetime(event_time).astimezone(get_farm_timezone(user))
    return localized.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def ensure_default_rules(db: Session, *, farm_id: int) -> list[AlertRule]:
    existing_rule_types = set(
        db.scalars(
            select(AlertRule.rule_type).where(
                AlertRule.farm_id == farm_id,
                AlertRule.source == "preset",
            )
        ).all()
    )

    created_rules: list[AlertRule] = []
    for definition in DEFAULT_RULE_DEFINITIONS:
        if definition["rule_type"] in existing_rule_types:
            continue

        rule = AlertRule(
            farm_id=farm_id,
            device_id=None,
            zone_name=None,
            is_enabled=True,
            **definition,
        )
        db.add(rule)
        created_rules.append(rule)

    if created_rules:
        db.flush()

    return created_rules


def load_available_rules(db: Session, *, farm_id: int, device_id: int | None) -> list[AlertRule]:
    ensure_default_rules(db, farm_id=farm_id)
    statement = select(AlertRule).where(
        AlertRule.farm_id == farm_id,
        AlertRule.is_enabled.is_(True),
    )
    if device_id is not None:
        statement = statement.where(or_(AlertRule.device_id.is_(None), AlertRule.device_id == device_id))
    else:
        statement = statement.where(AlertRule.device_id.is_(None))

    return list(
        db.scalars(
            statement.order_by(AlertRule.source.asc(), AlertRule.id.asc())
        ).all()
    )


def _find_next_event_time(db: Session, event: BehaviorEvent) -> datetime | None:
    next_occurred_at = db.scalar(
        select(BehaviorEvent.occurred_at)
        .where(
            BehaviorEvent.farm_id == event.farm_id,
            BehaviorEvent.device_id == event.device_id,
            or_(
                BehaviorEvent.occurred_at > event.occurred_at,
                (
                    (BehaviorEvent.occurred_at == event.occurred_at)
                    & (BehaviorEvent.id > event.id)
                ),
            ),
        )
        .order_by(BehaviorEvent.occurred_at.asc(), BehaviorEvent.id.asc())
        .limit(1)
    )
    return ensure_utc_datetime(next_occurred_at) if next_occurred_at else None


def estimate_event_duration_seconds(db: Session, event: BehaviorEvent) -> int:
    now_utc = datetime.now(timezone.utc)
    event_time = ensure_utc_datetime(event.occurred_at)
    next_event_time = _find_next_event_time(db, event)
    end_time = min(next_event_time, now_utc) if next_event_time else now_utc
    return max(0, int((end_time - event_time).total_seconds()))


def _find_last_drinking_event_time(db: Session, event: BehaviorEvent) -> datetime | None:
    previous_events = db.scalars(
        select(BehaviorEvent)
        .where(
            BehaviorEvent.farm_id == event.farm_id,
            BehaviorEvent.device_id == event.device_id,
            BehaviorEvent.occurred_at <= event.occurred_at,
        )
        .order_by(BehaviorEvent.occurred_at.desc(), BehaviorEvent.id.desc())
        .limit(200)
    ).all()

    for candidate in previous_events:
        if candidate.id == event.id:
            continue
        if canonical_behavior_key(candidate.behavior_type) == "drinking":
            return ensure_utc_datetime(candidate.occurred_at)
    return None


def _find_existing_open_device_alert(db: Session, *, rule_id: int, device_id: int | None) -> Alert | None:
    if device_id is None:
        return None
    return db.scalar(
        select(Alert)
        .where(
            Alert.rule_id == rule_id,
            Alert.device_id == device_id,
            Alert.status.in_(UNRESOLVED_ALERT_STATUSES),
        )
        .order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .limit(1)
    )


def _find_existing_event_alert(db: Session, *, rule_id: int, behavior_event_id: int) -> Alert | None:
    return db.scalar(
        select(Alert)
        .where(
            Alert.rule_id == rule_id,
            Alert.behavior_event_id == behavior_event_id,
        )
        .limit(1)
    )


def _build_alert_payload(
    *,
    rule: AlertRule,
    event: BehaviorEvent,
    title: str,
    description: str,
    snapshot: dict[str, Any],
) -> Alert:
    return Alert(
        farm_id=event.farm_id,
        rule_id=rule.id,
        behavior_event_id=event.id,
        device_id=event.device_id,
        device_code=event.device_code,
        title=title,
        description=description,
        severity=rule.severity,
        status="open",
        rule_source=rule.source,
        triggered_at=ensure_utc_datetime(event.occurred_at),
        snapshot=snapshot,
    )


def _matches_rule_scope(rule: AlertRule, event: BehaviorEvent) -> bool:
    if rule.device_id is not None and rule.device_id != event.device_id:
        return False
    if rule.zone_name and (event.zone_name or "").strip() != rule.zone_name.strip():
        return False
    if (
        rule.rule_type != "no_drinking"
        and rule.behavior_type
        and canonical_behavior_key(rule.behavior_type) != canonical_behavior_key(event.behavior_type)
    ):
        return False
    return True


def evaluate_alert_rules(
    db: Session,
    *,
    current_user: User,
    device: Device,
    events: list[BehaviorEvent],
) -> list[Alert]:
    active_rules = load_available_rules(db, farm_id=current_user.farm_id, device_id=device.id)
    created_alerts: list[Alert] = []

    for event in sorted(events, key=lambda item: (ensure_utc_datetime(item.occurred_at), item.id)):
        event_time = ensure_utc_datetime(event.occurred_at)
        event_duration_seconds = estimate_event_duration_seconds(db, event)
        event_duration_minutes = event_duration_seconds / 60
        event_behavior_key = canonical_behavior_key(event.behavior_type)

        for rule in active_rules:
            if not _matches_rule_scope(rule, event):
                continue

            threshold_minutes = max(rule.threshold_minutes, 1)
            alert_payload: Alert | None = None

            if rule.rule_type == "lying_duration":
                if event_behavior_key != "lying" or event_duration_minutes < threshold_minutes:
                    continue
                if _find_existing_event_alert(db, rule_id=rule.id, behavior_event_id=event.id):
                    continue
                alert_payload = _build_alert_payload(
                    rule=rule,
                    event=event,
                    title="牛只持续躺卧超时",
                    description=f"设备 {device.name} 于 {event.zone_name or '默认区域'} 识别到持续躺卧约 {int(event_duration_minutes)} 分钟，已超过阈值 {threshold_minutes} 分钟。",
                    snapshot={
                        "rule_type": rule.rule_type,
                        "behavior_type": event.behavior_type,
                        "zone_name": event.zone_name,
                        "duration_minutes": round(event_duration_minutes, 2),
                        "threshold_minutes": threshold_minutes,
                    },
                )

            elif rule.rule_type == "zone_dwell":
                if not event.zone_name or event_duration_minutes < threshold_minutes:
                    continue
                if _find_existing_event_alert(db, rule_id=rule.id, behavior_event_id=event.id):
                    continue
                alert_payload = _build_alert_payload(
                    rule=rule,
                    event=event,
                    title="牛只区域停留超时",
                    description=f"设备 {device.name} 识别到牛只在 {event.zone_name} 持续停留约 {int(event_duration_minutes)} 分钟，已超过阈值 {threshold_minutes} 分钟。",
                    snapshot={
                        "rule_type": rule.rule_type,
                        "behavior_type": event.behavior_type,
                        "zone_name": event.zone_name,
                        "duration_minutes": round(event_duration_minutes, 2),
                        "threshold_minutes": threshold_minutes,
                    },
                )

            elif rule.rule_type == "no_drinking":
                if event_behavior_key == "drinking":
                    continue
                existing_open_alert = _find_existing_open_device_alert(db, rule_id=rule.id, device_id=event.device_id)
                if existing_open_alert is not None:
                    continue

                last_drinking_time = _find_last_drinking_event_time(db, event)
                baseline_time = last_drinking_time or start_of_day_in_utc(event_time, current_user)
                gap_minutes = max(0, (event_time - baseline_time).total_seconds() / 60)
                if gap_minutes < threshold_minutes:
                    continue

                alert_payload = _build_alert_payload(
                    rule=rule,
                    event=event,
                    title="牛只长时间未进入饮水区",
                    description=f"设备 {device.name} 已约 {int(gap_minutes)} 分钟未识别到饮水行为，请检查饮水区状态和牛只健康情况。",
                    snapshot={
                        "rule_type": rule.rule_type,
                        "last_drinking_at": last_drinking_time.isoformat() if last_drinking_time else None,
                        "gap_minutes": round(gap_minutes, 2),
                        "threshold_minutes": threshold_minutes,
                    },
                )

            if alert_payload is None:
                continue

            db.add(alert_payload)
            created_alerts.append(alert_payload)

    if created_alerts:
        db.flush()

    return created_alerts
