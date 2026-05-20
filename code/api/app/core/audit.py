from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.models import AuditLog, User


def extract_client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def record_audit_log(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    user: User | None = None,
    farm_id: int | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        farm_id=farm_id if farm_id is not None else (user.farm_id if user else None),
        user_id=user.id if user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=extract_client_ip(request),
        detail=detail,
    )
    db.add(audit_log)
    return audit_log
