from __future__ import annotations

import time
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.security import ensure_csrf, safe_session_user


def db_session() -> Generator[Session, None, None]:
    yield from get_db()


def require_admin(request: Request) -> dict:
    user = safe_session_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def ensure_active_session(request: Request) -> None:
    settings = get_settings()
    now = int(time.time())
    last_seen = request.session.get("last_seen")
    if last_seen and now - int(last_seen) > settings.session_max_idle_seconds:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login?expired=1"})
    request.session["last_seen"] = now


def with_session_guard(request: Request, _: dict = Depends(require_admin)) -> None:
    ensure_active_session(request)
    ensure_csrf(request)
