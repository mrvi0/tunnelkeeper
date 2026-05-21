from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas import DestinationCreate, SSHKeyCreate, TunnelUserCreate, TunnelUserUpdate
from app.security import fingerprint_ssh_key, parse_public_key
from repositories.destination_repository import DestinationRepository
from repositories.ssh_key_repository import SSHKeyRepository
from repositories.tunnel_user_repository import TunnelUserRepository
from repositories.user_destination_repository import UserDestinationRepository
from services.exceptions import NotFoundError, ReadOnlyModeError, ValidationError
from services.linux_service import LinuxService
from services.user_provision_service import UserProvisionService

logger = logging.getLogger(__name__)


class TunnelAccessService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.user_repo = TunnelUserRepository(db)
        self.key_repo = SSHKeyRepository(db)
        self.dest_repo = DestinationRepository(db)
        self.user_dest_repo = UserDestinationRepository(db)
        self.linux_service = LinuxService()
        self.provision_service = UserProvisionService(db, linux_service=self.linux_service)

    def _assert_write_allowed(self) -> None:
        if self.settings.readonly_mode:
            raise ReadOnlyModeError("Readonly mode is enabled.")

    def _apply_tunnel_mode(self, payload: TunnelUserCreate | TunnelUserUpdate) -> dict:
        data = payload.model_dump()
        if getattr(payload, "tunnel_only", False):
            data["linux_shell"] = "/usr/sbin/nologin"
            if not data.get("force_command"):
                data["force_command"] = 'echo "Tunnel only";exit'
        else:
            if data.get("linux_shell") == "/usr/sbin/nologin" and not data.get("force_command"):
                data["linux_shell"] = "/bin/bash"
        data.pop("tunnel_only", None)
        data.pop("destination_ids", None)
        return data

    def _validate_destination_ids(self, destination_ids: list[int]) -> list[int]:
        unique = sorted(set(destination_ids))
        for dest_id in unique:
            dest = self.dest_repo.get(dest_id)
            if not dest:
                raise ValidationError(f"Destination {dest_id} not found.")
            if not dest.enabled:
                raise ValidationError(f"Destination '{dest.alias}' is disabled.")
        return unique

    def create_tunnel_user(self, payload: TunnelUserCreate):
        self._assert_write_allowed()
        if self.user_repo.get_by_username(payload.username):
            raise ValidationError("Username already exists.")
        destination_ids = self._validate_destination_ids(payload.destination_ids)
        user_data = self._apply_tunnel_mode(payload)
        user = self.user_repo.create(
            username=payload.username,
            comment=user_data["comment"],
            linux_home=user_data["linux_home"],
            linux_shell=user_data["linux_shell"],
            supplementary_groups=user_data["supplementary_groups"],
            allow_tcp_forwarding=user_data["allow_tcp_forwarding"],
            permit_tty=user_data["permit_tty"],
            x11_forwarding=user_data["x11_forwarding"],
            allow_agent_forwarding=user_data["allow_agent_forwarding"],
            force_command=user_data["force_command"],
        )
        self.linux_service.create_linux_user(user)
        self.user_dest_repo.set_destinations_for_user(user.id, destination_ids)
        self.provision_service.provision_user(user.id)
        return user

    def update_tunnel_user(self, tunnel_user_id: int, payload: TunnelUserUpdate):
        self._assert_write_allowed()
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        destination_ids = self._validate_destination_ids(payload.destination_ids)
        user_data = self._apply_tunnel_mode(payload)
        self.user_repo.update(
            user,
            comment=user_data["comment"],
            linux_shell=user_data["linux_shell"],
            supplementary_groups=user_data["supplementary_groups"],
            allow_tcp_forwarding=user_data["allow_tcp_forwarding"],
            permit_tty=user_data["permit_tty"],
            x11_forwarding=user_data["x11_forwarding"],
            allow_agent_forwarding=user_data["allow_agent_forwarding"],
            force_command=user_data["force_command"],
        )
        try:
            self.linux_service.update_linux_user(user)
        except Exception as exc:
            logger.warning("usermod failed for %s: %s", user.username, exc)
        self.user_dest_repo.set_destinations_for_user(user.id, destination_ids)
        self.provision_service.provision_user(user.id)
        return user

    def delete_tunnel_user(self, tunnel_user_id: int) -> None:
        self._assert_write_allowed()
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        self.linux_service.delete_linux_user(user)
        self.user_repo.delete(user)
        self.linux_service.reload_sshd()

    def add_ssh_key(self, payload: SSHKeyCreate):
        self._assert_write_allowed()
        user = self.user_repo.get(payload.tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        parse_public_key(payload.public_key)
        fingerprint = fingerprint_ssh_key(payload.public_key)
        try:
            key = self.key_repo.create(
                tunnel_user_id=payload.tunnel_user_id,
                name=payload.name,
                public_key=payload.public_key.strip(),
                fingerprint=fingerprint,
                enabled=payload.enabled,
            )
            self.provision_service.provision_user(user.id)
            return key
        except IntegrityError as exc:
            raise ValidationError("Duplicate key for this user.") from exc

    def toggle_key(self, key_id: int, enabled: bool) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        self.key_repo.set_enabled(key, enabled=enabled)
        self.provision_service.provision_user(key.tunnel_user_id)

    def delete_key(self, key_id: int) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        tunnel_user_id = key.tunnel_user_id
        self.key_repo.delete(key)
        self.provision_service.provision_user(tunnel_user_id)

    def add_destination(self, payload: DestinationCreate):
        self._assert_write_allowed()
        try:
            return self.dest_repo.create(
                alias=payload.alias,
                host=payload.host,
                port=payload.port,
                comment=payload.comment,
                enabled=payload.enabled,
            )
        except IntegrityError as exc:
            raise ValidationError("Destination with this host:port already exists.") from exc

    def toggle_destination(self, destination_id: int, enabled: bool) -> None:
        self._assert_write_allowed()
        dest = self.dest_repo.get(destination_id)
        if not dest:
            raise NotFoundError("Destination not found.")
        self.dest_repo.set_enabled(dest, enabled=enabled)
        user_ids = self.user_dest_repo.list_user_ids_for_destination(destination_id)
        for uid in user_ids:
            self.provision_service.provision_user(uid, reload_sshd=False)
        if user_ids:
            self.linux_service.reload_sshd()

    def delete_destination(self, destination_id: int) -> None:
        self._assert_write_allowed()
        dest = self.dest_repo.get(destination_id)
        if not dest:
            raise NotFoundError("Destination not found.")
        user_ids = self.user_dest_repo.list_user_ids_for_destination(destination_id)
        self.dest_repo.delete(dest)
        for uid in user_ids:
            self.provision_service.provision_user(uid, reload_sshd=False)
        if user_ids:
            self.linux_service.reload_sshd()

    def regenerate(self, tunnel_user_id: int) -> None:
        self._assert_write_allowed()
        self.provision_service.provision_user(tunnel_user_id)

    def sshd_include_warning(self) -> str | None:
        return self.linux_service.check_sshd_include()
