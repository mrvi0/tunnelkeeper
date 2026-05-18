from __future__ import annotations

import logging
from typing import Any, Callable
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import db_session, require_admin, with_session_guard
from app.config import get_settings
from app.schemas import PermitOpenCreate, SSHKeyCreate, TunnelUserCreate
from app.security import ensure_csrf, validate_csrf
from models.permit_open_rule import PermitOpenRule
from models.ssh_key import SSHKey
from models.tunnel_user import TunnelUser
from repositories.audit_repository import AuditRepository
from services.exceptions import AppError
from services.tunnel_access_service import TunnelAccessService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _dashboard_context(db: Session) -> dict[str, Any]:
    users = list(db.scalars(select(TunnelUser).order_by(TunnelUser.created_at.desc())).all())
    keys_count = len(db.scalars(select(SSHKey.id)).all())
    rules_count = len(db.scalars(select(PermitOpenRule.id)).all())
    latest_audit = AuditRepository(db).latest(limit=15)
    return {
        "users": users,
        "users_count": len(users),
        "keys_count": keys_count,
        "rules_count": rules_count,
        "latest_audit": latest_audit,
    }


def _perform_mutation(
    *,
    db: Session,
    actor: str,
    action: str,
    target: str,
    details: str,
    execute: Callable[[], None],
) -> tuple[bool, str]:
    try:
        execute()
        AuditRepository(db).create(actor=actor, action=action, target=target, details=details)
        db.commit()
        return True, "Operation completed"
    except AppError as exc:
        db.rollback()
        logger.warning("Domain error action=%s target=%s error=%s", action, target, exc)
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Unexpected mutation failure")
        return False, f"Unexpected error: {exc}"


@router.get("/")
def dashboard(
    request: Request,
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    context = _dashboard_context(db)
    context.update(
        {
            "admin": admin,
            "csrf_token": ensure_csrf(request),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
            "readonly_mode": settings.readonly_mode,
        }
    )
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


@router.get("/users/{user_id}")
def user_details(
    user_id: int,
    request: Request,
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    user = db.get(TunnelUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    keys = list(
        db.scalars(
            select(SSHKey).where(SSHKey.tunnel_user_id == user_id).order_by(SSHKey.created_at.desc())
        ).all()
    )
    rules = list(
        db.scalars(
            select(PermitOpenRule)
            .where(PermitOpenRule.tunnel_user_id == user_id)
            .order_by(PermitOpenRule.created_at.desc())
        ).all()
    )
    return templates.TemplateResponse(
        request=request,
        name="user_detail.html",
        context={
            "admin": admin,
            "user": user,
            "keys": keys,
            "rules": rules,
            "csrf_token": ensure_csrf(request),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
            "readonly_mode": settings.readonly_mode,
        },
    )


@router.post("/users")
def create_user(
    request: Request,
    username: str = Form(...),
    comment: str = Form(""),
    linux_home: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    payload = TunnelUserCreate(username=username, comment=comment, linux_home=linux_home)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="create_tunnel_user",
        target=f"user:{username}",
        details=f"home={payload.linux_home}",
        execute=lambda: service.create_tunnel_user(payload),
    )
    if ok:
        return RedirectResponse(url="/?message=User%20created", status_code=303)
    return RedirectResponse(url=f"/?error={quote_plus(result)}", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="delete_tunnel_user",
        target=f"user_id:{user_id}",
        details="deleted user and related rules/keys",
        execute=lambda: service.delete_tunnel_user(user_id),
    )
    if ok:
        return RedirectResponse(url="/?message=User%20deleted", status_code=303)
    return RedirectResponse(url=f"/?error={quote_plus(result)}", status_code=303)


@router.post("/users/{user_id}/comment")
def update_user_comment(
    user_id: int,
    request: Request,
    comment: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    user = db.get(TunnelUser, user_id)
    if not user:
        return RedirectResponse(url="/?error=User%20not%20found", status_code=303)
    user.comment = comment
    db.add(user)
    AuditRepository(db).create(
        actor=admin["username"],
        action="update_tunnel_user_comment",
        target=f"user_id:{user_id}",
        details=f"comment={comment}",
    )
    db.commit()
    return RedirectResponse(url=f"/users/{user_id}?message=Comment%20updated", status_code=303)


@router.post("/users/{user_id}/keys")
def add_key(
    user_id: int,
    request: Request,
    name: str = Form(...),
    public_key: str = Form(...),
    enabled: bool = Form(True),
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    payload = SSHKeyCreate(name=name, public_key=public_key, enabled=enabled)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="add_ssh_key",
        target=f"user_id:{user_id}",
        details=f"key_name={name}",
        execute=lambda: service.add_ssh_key(user_id, payload),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=Key%20added", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)


@router.post("/keys/{key_id}/toggle")
def toggle_key(
    key_id: int,
    request: Request,
    enabled: bool = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    key = db.get(SSHKey, key_id)
    if not key:
        return RedirectResponse(url="/?error=Key%20not%20found", status_code=303)
    service = TunnelAccessService(db)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="toggle_ssh_key",
        target=f"key_id:{key_id}",
        details=f"enabled={enabled}",
        execute=lambda: service.toggle_key(key_id, enabled),
    )
    if ok:
        return RedirectResponse(url=f"/users/{key.tunnel_user_id}?message=Key%20updated", status_code=303)
    return RedirectResponse(url=f"/users/{key.tunnel_user_id}?error={quote_plus(result)}", status_code=303)


@router.post("/keys/{key_id}/delete")
def delete_key(
    key_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    key = db.get(SSHKey, key_id)
    if not key:
        return RedirectResponse(url="/?error=Key%20not%20found", status_code=303)
    user_id = key.tunnel_user_id
    service = TunnelAccessService(db)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="delete_ssh_key",
        target=f"key_id:{key_id}",
        details="deleted",
        execute=lambda: service.delete_key(key_id),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=Key%20deleted", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)


@router.post("/users/{user_id}/rules")
def add_rule(
    user_id: int,
    request: Request,
    alias: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    comment: str = Form(""),
    enabled: bool = Form(True),
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    payload = PermitOpenCreate(alias=alias, host=host, port=port, comment=comment, enabled=enabled)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="add_permit_rule",
        target=f"user_id:{user_id}",
        details=f"{host}:{port}",
        execute=lambda: service.add_permit_rule(user_id, payload),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=Rule%20added", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)


@router.post("/rules/{rule_id}/toggle")
def toggle_rule(
    rule_id: int,
    request: Request,
    enabled: bool = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    rule = db.get(PermitOpenRule, rule_id)
    if not rule:
        return RedirectResponse(url="/?error=Rule%20not%20found", status_code=303)
    service = TunnelAccessService(db)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="toggle_permit_rule",
        target=f"rule_id:{rule_id}",
        details=f"enabled={enabled}",
        execute=lambda: service.toggle_rule(rule_id, enabled),
    )
    if ok:
        return RedirectResponse(url=f"/users/{rule.tunnel_user_id}?message=Rule%20updated", status_code=303)
    return RedirectResponse(url=f"/users/{rule.tunnel_user_id}?error={quote_plus(result)}", status_code=303)


@router.post("/rules/{rule_id}/delete")
def delete_rule(
    rule_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    rule = db.get(PermitOpenRule, rule_id)
    if not rule:
        return RedirectResponse(url="/?error=Rule%20not%20found", status_code=303)
    user_id = rule.tunnel_user_id
    service = TunnelAccessService(db)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="delete_permit_rule",
        target=f"rule_id:{rule_id}",
        details="deleted",
        execute=lambda: service.delete_rule(rule_id),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=Rule%20deleted", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)


@router.post("/users/{user_id}/regenerate")
def regenerate_user_keys(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="manual_regenerate_authorized_keys",
        target=f"user_id:{user_id}",
        details="manual trigger",
        execute=lambda: service.regenerate(user_id),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=authorized_keys%20regenerated", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)
