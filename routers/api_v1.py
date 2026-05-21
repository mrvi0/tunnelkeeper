from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api_auth import require_api_token
from app.api_schemas import (
    AuditOut,
    DestinationCreateIn,
    DestinationOut,
    DestinationPatch,
    EnabledPatch,
    HealthOut,
    MessageOut,
    SSHKeyCreateBody,
    SSHKeyOut,
    TunnelUserCreateIn,
    TunnelUserDetailOut,
    TunnelUserOut,
    TunnelUserUpdateIn,
)
from app.config import get_settings
from app.dependencies import db_session
from app.schemas import SSHKeyCreate
from repositories.audit_repository import AuditRepository
from repositories.destination_repository import DestinationRepository
from repositories.ssh_key_repository import SSHKeyRepository
from repositories.tunnel_user_repository import TunnelUserRepository
from repositories.user_destination_repository import UserDestinationRepository
from services.exceptions import AppError, NotFoundError, ReadOnlyModeError, ValidationError
from services.tunnel_access_service import TunnelAccessService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1", tags=["api"], dependencies=[Depends(require_api_token)])


def _http_error(exc: AppError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ReadOnlyModeError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def _run_mutation(
    *,
    db: Session,
    action: str,
    target: str,
    details: str,
    execute: Callable[[], Any],
) -> Any:
    try:
        result = execute()
        AuditRepository(db).create(actor="api", action=action, target=target, details=details)
        db.commit()
        return result
    except AppError as exc:
        db.rollback()
        raise _http_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("API mutation failed action=%s target=%s", action, target)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


def _user_out(user, *, destination_ids: list[int] | None = None) -> TunnelUserOut:
    return TunnelUserOut(
        id=user.id,
        username=user.username,
        comment=user.comment,
        linux_home=user.linux_home,
        linux_shell=user.linux_shell,
        supplementary_groups=user.supplementary_groups,
        allow_tcp_forwarding=user.allow_tcp_forwarding,
        permit_tty=user.permit_tty,
        x11_forwarding=user.x11_forwarding,
        allow_agent_forwarding=user.allow_agent_forwarding,
        force_command=user.force_command,
        created_at=user.created_at,
        destination_ids=destination_ids if destination_ids is not None else [d.id for d in user.destinations],
        sshd_config_path=str(Path(settings.sshd_generated_dir) / user.sshd_config_filename),
    )


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(db_session)) -> HealthOut:
    service = TunnelAccessService(db)
    return HealthOut(
        status="ok",
        readonly_mode=settings.readonly_mode,
        enable_web_ui=settings.enable_web_ui,
        enable_api=settings.enable_api,
        sshd_warning=service.sshd_include_warning(),
    )


@router.get("/destinations", response_model=list[DestinationOut])
def list_destinations(db: Session = Depends(db_session)) -> list[DestinationOut]:
    return DestinationRepository(db).list_all()


@router.post("/destinations", response_model=DestinationOut, status_code=status.HTTP_201_CREATED)
def create_destination(payload: DestinationCreateIn, db: Session = Depends(db_session)) -> DestinationOut:
    service = TunnelAccessService(db)
    dest = _run_mutation(
        db=db,
        action="add_destination",
        target=f"{payload.host}:{payload.port}",
        details=f"alias={payload.alias}",
        execute=lambda: service.add_destination(payload),
    )
    return dest


@router.get("/destinations/{dest_id}", response_model=DestinationOut)
def get_destination(dest_id: int, db: Session = Depends(db_session)) -> DestinationOut:
    dest = DestinationRepository(db).get(dest_id)
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found.")
    return dest


@router.patch("/destinations/{dest_id}", response_model=DestinationOut)
def patch_destination(
    dest_id: int,
    payload: DestinationPatch,
    db: Session = Depends(db_session),
) -> DestinationOut:
    repo = DestinationRepository(db)
    dest = repo.get(dest_id)
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found.")
    service = TunnelAccessService(db)
    data = payload.model_dump(exclude_unset=True)
    if "enabled" in data and len(data) == 1:
        _run_mutation(
            db=db,
            action="toggle_destination",
            target=f"dest_id:{dest_id}",
            details=f"enabled={data['enabled']}",
            execute=lambda: service.toggle_destination(dest_id, data["enabled"]),
        )
        db.refresh(dest)
        return dest
    if data:
        service._assert_write_allowed()
        for key, value in data.items():
            setattr(dest, key, value)
        db.flush()
        user_ids = UserDestinationRepository(db).list_user_ids_for_destination(dest_id)
        for uid in user_ids:
            service.provision_service.provision_user(uid, reload_sshd=False)
        if user_ids:
            service.linux_service.reload_sshd()
        _run_mutation(
            db=db,
            action="update_destination",
            target=f"dest_id:{dest_id}",
            details=str(data),
            execute=lambda: dest,
        )
    db.refresh(dest)
    return dest


@router.delete("/destinations/{dest_id}", response_model=MessageOut)
def delete_destination(dest_id: int, db: Session = Depends(db_session)) -> MessageOut:
    service = TunnelAccessService(db)
    _run_mutation(
        db=db,
        action="delete_destination",
        target=f"dest_id:{dest_id}",
        details="deleted",
        execute=lambda: service.delete_destination(dest_id),
    )
    return MessageOut(message="Destination deleted")


@router.get("/users", response_model=list[TunnelUserOut])
def list_users(db: Session = Depends(db_session)) -> list[TunnelUserOut]:
    users = TunnelUserRepository(db).list()
    return [_user_out(u) for u in users]


@router.post("/users", response_model=TunnelUserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: TunnelUserCreateIn, db: Session = Depends(db_session)) -> TunnelUserOut:
    service = TunnelAccessService(db)
    user = _run_mutation(
        db=db,
        action="create_tunnel_user",
        target=f"user:{payload.username}",
        details=f"destinations={payload.destination_ids}",
        execute=lambda: service.create_tunnel_user(payload),
    )
    db.refresh(user)
    return _user_out(user)


@router.get("/users/{user_id}", response_model=TunnelUserDetailOut)
def get_user(user_id: int, db: Session = Depends(db_session)) -> TunnelUserDetailOut:
    user = TunnelUserRepository(db).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Tunnel user not found.")
    base = _user_out(user)
    return TunnelUserDetailOut(
        **base.model_dump(),
        keys=[SSHKeyOut.model_validate(k) for k in user.ssh_keys],
        destinations=[DestinationOut.model_validate(d) for d in user.destinations],
    )


@router.patch("/users/{user_id}", response_model=TunnelUserOut)
def update_user(
    user_id: int,
    payload: TunnelUserUpdateIn,
    db: Session = Depends(db_session),
) -> TunnelUserOut:
    service = TunnelAccessService(db)
    user = _run_mutation(
        db=db,
        action="update_tunnel_user",
        target=f"user_id:{user_id}",
        details=f"destinations={payload.destination_ids}",
        execute=lambda: service.update_tunnel_user(user_id, payload),
    )
    db.refresh(user)
    return _user_out(user)


@router.delete("/users/{user_id}", response_model=MessageOut)
def delete_user(user_id: int, db: Session = Depends(db_session)) -> MessageOut:
    service = TunnelAccessService(db)
    _run_mutation(
        db=db,
        action="delete_tunnel_user",
        target=f"user_id:{user_id}",
        details="deleted",
        execute=lambda: service.delete_tunnel_user(user_id),
    )
    return MessageOut(message="User deleted")


@router.post("/users/{user_id}/regenerate", response_model=MessageOut)
def regenerate_user(user_id: int, db: Session = Depends(db_session)) -> MessageOut:
    service = TunnelAccessService(db)
    _run_mutation(
        db=db,
        action="provision_user",
        target=f"user_id:{user_id}",
        details="api",
        execute=lambda: service.regenerate(user_id),
    )
    return MessageOut(message="Provisioned")


@router.get("/users/{user_id}/keys", response_model=list[SSHKeyOut])
def list_user_keys(user_id: int, db: Session = Depends(db_session)) -> list[SSHKeyOut]:
    if not TunnelUserRepository(db).get(user_id):
        raise HTTPException(status_code=404, detail="Tunnel user not found.")
    return SSHKeyRepository(db).list_by_user(user_id)


@router.post("/users/{user_id}/keys", response_model=SSHKeyOut, status_code=status.HTTP_201_CREATED)
def add_user_key(
    user_id: int,
    payload: SSHKeyCreateBody,
    db: Session = Depends(db_session),
) -> SSHKeyOut:
    service = TunnelAccessService(db)
    body = SSHKeyCreate(tunnel_user_id=user_id, **payload.model_dump())
    key = _run_mutation(
        db=db,
        action="add_ssh_key",
        target=f"user_id:{user_id}",
        details=f"key_name={payload.name}",
        execute=lambda: service.add_ssh_key(body),
    )
    return key


@router.patch("/keys/{key_id}", response_model=SSHKeyOut)
def patch_key(key_id: int, payload: EnabledPatch, db: Session = Depends(db_session)) -> SSHKeyOut:
    service = TunnelAccessService(db)
    _run_mutation(
        db=db,
        action="toggle_ssh_key",
        target=f"key_id:{key_id}",
        details=f"enabled={payload.enabled}",
        execute=lambda: service.toggle_key(key_id, payload.enabled),
    )
    key = SSHKeyRepository(db).get(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="SSH key not found.")
    return key


@router.delete("/keys/{key_id}", response_model=MessageOut)
def delete_key(key_id: int, db: Session = Depends(db_session)) -> MessageOut:
    service = TunnelAccessService(db)
    _run_mutation(
        db=db,
        action="delete_ssh_key",
        target=f"key_id:{key_id}",
        details="deleted",
        execute=lambda: service.delete_key(key_id),
    )
    return MessageOut(message="Key deleted")


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(db_session),
) -> list[AuditOut]:
    return AuditRepository(db).latest(limit=limit)
