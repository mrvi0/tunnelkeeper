from __future__ import annotations

import logging
from typing import Annotated, Any, Callable
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import db_session, require_admin, with_session_guard
from app.schemas import SHELL_CHOICES, DestinationCreate, SSHKeyCreate, TunnelUserCreate, TunnelUserUpdate
from app.security import ensure_csrf, validate_csrf
from models.tunnel_user import TunnelUser
from repositories.audit_repository import AuditRepository
from repositories.destination_repository import DestinationRepository
from repositories.ssh_key_repository import SSHKeyRepository
from services.exceptions import AppError
from services.tunnel_access_service import TunnelAccessService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def _form_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("true", "1", "on", "yes")
templates = Jinja2Templates(directory="templates")


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


def _dashboard_context(db: Session, service: TunnelAccessService) -> dict[str, Any]:
    users = list(db.scalars(select(TunnelUser).order_by(TunnelUser.created_at.desc())).all())
    keys_count = SSHKeyRepository(db).count()
    destinations_count = DestinationRepository(db).count()
    return {
        "users": users,
        "users_count": len(users),
        "keys_count": keys_count,
        "destinations_count": destinations_count,
        "latest_audit": AuditRepository(db).latest(limit=15),
        "sshd_warning": service.sshd_include_warning(),
    }


@router.get("/")
def dashboard(
    request: Request,
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    service = TunnelAccessService(db)
    context = _dashboard_context(db, service)
    context.update(
        {
            "admin": admin,
            "csrf_token": ensure_csrf(request),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
            "readonly_mode": settings.readonly_mode,
            "destinations": DestinationRepository(db).list_all(),
            "shell_choices": SHELL_CHOICES,
        }
    )
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


@router.get("/destinations")
def destinations_page(
    request: Request,
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    rules = DestinationRepository(db).list_all()
    return templates.TemplateResponse(
        request=request,
        name="destinations.html",
        context={
            "admin": admin,
            "destinations": rules,
            "csrf_token": ensure_csrf(request),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
            "readonly_mode": settings.readonly_mode,
        },
    )


@router.post("/destinations")
def create_destination(
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
    payload = DestinationCreate(alias=alias, host=host, port=port, comment=comment, enabled=enabled)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="add_destination",
        target=f"{host}:{port}",
        details=f"alias={alias}",
        execute=lambda: service.add_destination(payload),
    )
    if ok:
        return RedirectResponse(url="/destinations?message=Destination%20added", status_code=303)
    return RedirectResponse(url=f"/destinations?error={quote_plus(result)}", status_code=303)


@router.post("/destinations/{dest_id}/toggle")
def toggle_destination(
    dest_id: int,
    request: Request,
    enabled: bool = Form(...),
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
        action="toggle_destination",
        target=f"dest_id:{dest_id}",
        details=f"enabled={enabled}",
        execute=lambda: service.toggle_destination(dest_id, enabled),
    )
    if ok:
        return RedirectResponse(url="/destinations?message=Destination%20updated", status_code=303)
    return RedirectResponse(url=f"/destinations?error={quote_plus(result)}", status_code=303)


@router.post("/destinations/{dest_id}/delete")
def delete_destination(
    dest_id: int,
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
        action="delete_destination",
        target=f"dest_id:{dest_id}",
        details="deleted",
        execute=lambda: service.delete_destination(dest_id),
    )
    if ok:
        return RedirectResponse(url="/destinations?message=Destination%20deleted", status_code=303)
    return RedirectResponse(url=f"/destinations?error={quote_plus(result)}", status_code=303)


@router.get("/users/{user_id}")
def user_details(
    user_id: int,
    request: Request,
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    from repositories.tunnel_user_repository import TunnelUserRepository
    from repositories.user_destination_repository import UserDestinationRepository

    user = TunnelUserRepository(db).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    keys = SSHKeyRepository(db).list_by_user(user_id)
    assigned_dest_ids = set(UserDestinationRepository(db).list_destination_ids(user_id))
    all_destinations = DestinationRepository(db).list_all()
    return templates.TemplateResponse(
        request=request,
        name="user_detail.html",
        context={
            "admin": admin,
            "user": user,
            "keys": keys,
            "all_destinations": all_destinations,
            "assigned_dest_ids": assigned_dest_ids,
            "csrf_token": ensure_csrf(request),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
            "readonly_mode": settings.readonly_mode,
            "shell_choices": SHELL_CHOICES,
            "sshd_path": f"{settings.sshd_generated_dir}/{user.sshd_config_filename}",
        },
    )


@router.post("/users")
def create_user(
    request: Request,
    username: str = Form(...),
    comment: str = Form(""),
    linux_home: str = Form(""),
    linux_shell: str = Form("nologin"),
    supplementary_groups: str = Form(""),
    allow_tcp_forwarding: str | None = Form(None),
    permit_tty: str | None = Form(None),
    x11_forwarding: str | None = Form(None),
    allow_agent_forwarding: str | None = Form(None),
    force_command: str = Form(""),
    tunnel_only: str | None = Form(None),
    destination_ids: Annotated[list[int], Form()] = [],
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    payload = TunnelUserCreate(
        username=username,
        comment=comment,
        linux_home=linux_home,
        linux_shell=linux_shell,
        supplementary_groups=supplementary_groups,
        allow_tcp_forwarding=_form_bool(allow_tcp_forwarding, default=True),
        permit_tty=_form_bool(permit_tty),
        x11_forwarding=_form_bool(x11_forwarding),
        allow_agent_forwarding=_form_bool(allow_agent_forwarding),
        force_command=force_command,
        tunnel_only=_form_bool(tunnel_only, default=True),
        destination_ids=destination_ids,
    )
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="create_tunnel_user",
        target=f"user:{username}",
        details=f"destinations={destination_ids}",
        execute=lambda: service.create_tunnel_user(payload),
    )
    if ok:
        return RedirectResponse(url="/?message=User%20created", status_code=303)
    return RedirectResponse(url=f"/?error={quote_plus(result)}", status_code=303)


@router.post("/users/{user_id}/update")
def update_user(
    user_id: int,
    request: Request,
    comment: str = Form(""),
    linux_shell: str = Form("nologin"),
    supplementary_groups: str = Form(""),
    allow_tcp_forwarding: str | None = Form(None),
    permit_tty: str | None = Form(None),
    x11_forwarding: str | None = Form(None),
    allow_agent_forwarding: str | None = Form(None),
    force_command: str = Form(""),
    tunnel_only: str | None = Form(None),
    destination_ids: Annotated[list[int], Form()] = [],
    csrf_token: str = Form(...),
    db: Session = Depends(db_session),
    admin: dict = Depends(require_admin),
    _: None = Depends(with_session_guard),
):
    validate_csrf(request, csrf_token)
    service = TunnelAccessService(db)
    payload = TunnelUserUpdate(
        comment=comment,
        linux_shell=linux_shell,
        supplementary_groups=supplementary_groups,
        allow_tcp_forwarding=_form_bool(allow_tcp_forwarding, default=True),
        permit_tty=_form_bool(permit_tty),
        x11_forwarding=_form_bool(x11_forwarding),
        allow_agent_forwarding=_form_bool(allow_agent_forwarding),
        force_command=force_command,
        tunnel_only=_form_bool(tunnel_only),
        destination_ids=destination_ids,
    )
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="update_tunnel_user",
        target=f"user_id:{user_id}",
        details=f"destinations={destination_ids}",
        execute=lambda: service.update_tunnel_user(user_id, payload),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=User%20updated", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)


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
        details="deleted",
        execute=lambda: service.delete_tunnel_user(user_id),
    )
    if ok:
        return RedirectResponse(url="/?message=User%20deleted", status_code=303)
    return RedirectResponse(url=f"/?error={quote_plus(result)}", status_code=303)


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
    payload = SSHKeyCreate(tunnel_user_id=user_id, name=name, public_key=public_key, enabled=enabled)
    ok, result = _perform_mutation(
        db=db,
        actor=admin["username"],
        action="add_ssh_key",
        target=f"user_id:{user_id}",
        details=f"key_name={name}",
        execute=lambda: service.add_ssh_key(payload),
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
    from models.ssh_key import SSHKey

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
    from models.ssh_key import SSHKey

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


@router.post("/users/{user_id}/regenerate")
def regenerate_user(
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
        action="provision_user",
        target=f"user_id:{user_id}",
        details="manual",
        execute=lambda: service.regenerate(user_id),
    )
    if ok:
        return RedirectResponse(url=f"/users/{user_id}?message=Provisioned", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?error={quote_plus(result)}", status_code=303)
