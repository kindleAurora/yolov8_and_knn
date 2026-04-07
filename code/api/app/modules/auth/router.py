from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.responses import success_response
from app.core.audit import record_audit_log
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.models import User, UserRole
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


class FarmSummary(BaseModel):
    id: int
    name: str
    timezone: str

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    id: int
    username: str
    display_name: str
    status: str
    farm: FarmSummary
    roles: list[str]


class LoginPayload(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserSummary


def _user_query():
    return select(User).options(
        selectinload(User.farm),
        selectinload(User.role_links).selectinload(UserRole.role),
    )


def _serialize_user(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        farm=FarmSummary.model_validate(user.farm),
        roles=user.role_codes,
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.scalar(_user_query().where(User.username == payload.username))

    if user is None or not verify_password(payload.password, user.password_hash):
        record_audit_log(
            db,
            action="auth.login_failed",
            target_type="user",
            detail={"username": payload.username},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.status != "active":
        record_audit_log(
            db,
            action="auth.login_rejected",
            target_type="user",
            target_id=str(user.id),
            user=user,
            detail={"reason": "inactive"},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号已停用",
        )

    user.last_login_at = datetime.now(timezone.utc)
    record_audit_log(
        db,
        action="auth.login_succeeded",
        target_type="user",
        target_id=str(user.id),
        user=user,
        detail={"roles": user.role_codes},
        request=request,
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return success_response(
        LoginPayload(
            access_token=token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60,
            user=_serialize_user(user),
        ).model_dump()
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict[str, object]:
    return success_response(_serialize_user(current_user).model_dump())


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    record_audit_log(
        db,
        action="auth.logout",
        target_type="user",
        target_id=str(current_user.id),
        user=current_user,
        request=request,
    )
    db.commit()
    return success_response({"logged_out": True}, message="已退出登录")
