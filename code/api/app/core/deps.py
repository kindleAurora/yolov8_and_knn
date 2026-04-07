from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.models import User, UserRole
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _base_user_query() -> Select[tuple[User]]:
    return select(User).options(
        selectinload(User.farm),
        selectinload(User.role_links).selectinload(UserRole.role),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再访问",
        )

    try:
        user_id = decode_access_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效或已过期",
        ) from exc

    user = db.scalar(_base_user_query().where(User.id == user_id))
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前用户不可用",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前操作仅管理员可用",
        )
    return user
