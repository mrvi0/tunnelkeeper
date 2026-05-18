from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas import PermitOpenCreate, SSHKeyCreate, TunnelUserCreate
from app.security import fingerprint_ssh_key, parse_public_key
from repositories.permit_open_repository import PermitOpenRepository
from repositories.ssh_key_repository import SSHKeyRepository
from repositories.tunnel_user_repository import TunnelUserRepository
from services.authorized_keys_service import AuthorizedKeysService
from services.exceptions import NotFoundError, ReadOnlyModeError, ValidationError
from services.linux_service import LinuxService

logger = logging.getLogger(__name__)


class TunnelAccessService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.user_repo = TunnelUserRepository(db)
        self.key_repo = SSHKeyRepository(db)
        self.rule_repo = PermitOpenRepository(db)
        self.linux_service = LinuxService()
        self.auth_keys_service = AuthorizedKeysService(db, linux_service=self.linux_service)

    def _assert_write_allowed(self) -> None:
        if self.settings.readonly_mode:
            raise ReadOnlyModeError("Readonly mode is enabled.")

    def create_tunnel_user(self, payload: TunnelUserCreate):
        self._assert_write_allowed()
        if self.user_repo.get_by_username(payload.username):
            raise ValidationError("Username already exists.")

        user = self.user_repo.create(
            username=payload.username,
            comment=payload.comment,
            linux_home=payload.linux_home,
        )
        self.linux_service.create_linux_user(user.username, user.linux_home)
        self.linux_service.ensure_ssh_directory(user)
        self.auth_keys_service.regenerate(user.id)
        return user

    def delete_tunnel_user(self, tunnel_user_id: int) -> None:
        self._assert_write_allowed()
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        self.user_repo.delete(user)

    def add_ssh_key(self, tunnel_user_id: int, payload: SSHKeyCreate):
        self._assert_write_allowed()
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        parse_public_key(payload.public_key)
        fingerprint = fingerprint_ssh_key(payload.public_key)
        try:
            key = self.key_repo.create(
                tunnel_user_id=tunnel_user_id,
                name=payload.name,
                public_key=payload.public_key.strip(),
                fingerprint=fingerprint,
                enabled=payload.enabled,
            )
            self.auth_keys_service.regenerate(tunnel_user_id)
            return key
        except IntegrityError as exc:
            raise ValidationError("Duplicate key for this user.") from exc

    def toggle_key(self, key_id: int, enabled: bool) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        self.key_repo.set_enabled(key, enabled=enabled)
        self.auth_keys_service.regenerate(key.tunnel_user_id)

    def delete_key(self, key_id: int) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        tunnel_user_id = key.tunnel_user_id
        self.key_repo.delete(key)
        self.auth_keys_service.regenerate(tunnel_user_id)

    def add_permit_rule(self, tunnel_user_id: int, payload: PermitOpenCreate):
        self._assert_write_allowed()
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        try:
            rule = self.rule_repo.create(
                tunnel_user_id=tunnel_user_id,
                alias=payload.alias,
                host=payload.host,
                port=payload.port,
                comment=payload.comment,
                enabled=payload.enabled,
            )
            self.auth_keys_service.regenerate(tunnel_user_id)
            return rule
        except IntegrityError as exc:
            raise ValidationError("Duplicate host:port rule for this user.") from exc

    def toggle_rule(self, rule_id: int, enabled: bool) -> None:
        self._assert_write_allowed()
        rule = self.rule_repo.get(rule_id)
        if not rule:
            raise NotFoundError("PermitOpen rule not found.")
        self.rule_repo.set_enabled(rule, enabled=enabled)
        self.auth_keys_service.regenerate(rule.tunnel_user_id)

    def delete_rule(self, rule_id: int) -> None:
        self._assert_write_allowed()
        rule = self.rule_repo.get(rule_id)
        if not rule:
            raise NotFoundError("PermitOpen rule not found.")
        tunnel_user_id = rule.tunnel_user_id
        self.rule_repo.delete(rule)
        self.auth_keys_service.regenerate(tunnel_user_id)

    def regenerate(self, tunnel_user_id: int) -> None:
        self._assert_write_allowed()
        self.auth_keys_service.regenerate(tunnel_user_id)
