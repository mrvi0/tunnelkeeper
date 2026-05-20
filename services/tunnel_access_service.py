from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas import PermitOpenCreate, SSHKeyCreate, TunnelUserCreate
from app.security import fingerprint_ssh_key, parse_public_key
from repositories.key_assignment_repository import KeyAssignmentRepository
from repositories.key_permit_repository import KeyPermitRepository
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
        self.key_permit_repo = KeyPermitRepository(db)
        self.assignment_repo = KeyAssignmentRepository(db)
        self.linux_service = LinuxService()
        self.auth_keys_service = AuthorizedKeysService(db, linux_service=self.linux_service)

    def _assert_write_allowed(self) -> None:
        if self.settings.readonly_mode:
            raise ReadOnlyModeError("Readonly mode is enabled.")

    def _validate_users_and_rules(
        self,
        tunnel_user_ids: list[int],
        permit_rule_ids: list[int],
    ) -> tuple[list[int], dict[int, list[int]]]:
        user_ids = sorted(set(tunnel_user_ids))
        if not user_ids:
            raise ValidationError("Select at least one tunnel user for this key.")

        for user_id in user_ids:
            if not self.user_repo.get(user_id):
                raise ValidationError(f"Tunnel user {user_id} not found.")

        rules_by_user: dict[int, list[int]] = defaultdict(list)
        for rule_id in sorted(set(permit_rule_ids)):
            rule = self.rule_repo.get(rule_id)
            if not rule:
                raise ValidationError(f"PermitOpen rule {rule_id} not found.")
            if rule.tunnel_user_id not in user_ids:
                raise ValidationError(
                    f"Rule '{rule.alias}' belongs to a user that is not selected for this key."
                )
            if not rule.enabled:
                raise ValidationError(f"Rule '{rule.alias}' is disabled.")
            rules_by_user[rule.tunnel_user_id].append(rule_id)

        for user_id in user_ids:
            if not rules_by_user.get(user_id):
                user = self.user_repo.get(user_id)
                name = user.username if user else str(user_id)
                raise ValidationError(f"Select at least one PermitOpen rule for user '{name}'.")

        return user_ids, dict(rules_by_user)

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
        self.linux_service.delete_linux_user(user.username, user.linux_home)
        self.user_repo.delete(user)

    def add_ssh_key(
        self,
        payload: SSHKeyCreate,
        tunnel_user_ids: list[int],
        permit_rule_ids: list[int],
    ):
        self._assert_write_allowed()
        parse_public_key(payload.public_key)
        fingerprint = fingerprint_ssh_key(payload.public_key)
        user_ids, rules_by_user = self._validate_users_and_rules(tunnel_user_ids, permit_rule_ids)

        try:
            key = self.key_repo.create(
                name=payload.name,
                public_key=payload.public_key.strip(),
                fingerprint=fingerprint,
                enabled=payload.enabled,
            )
            self.assignment_repo.set_users_for_key(key.id, user_ids)
            for user_id, rule_ids in rules_by_user.items():
                self.key_permit_repo.set_rules_for_key_user(key.id, user_id, rule_ids)
            self.auth_keys_service.regenerate_many(user_ids)
            return key
        except IntegrityError as exc:
            raise ValidationError("This public key already exists in the system.") from exc

    def set_key_access_for_user(
        self,
        key_id: int,
        tunnel_user_id: int,
        permit_rule_ids: list[int],
    ) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        if tunnel_user_id not in self.assignment_repo.list_user_ids_for_key(key_id):
            raise ValidationError("Key is not assigned to this tunnel user.")

        _, rules_by_user = self._validate_users_and_rules([tunnel_user_id], permit_rule_ids)
        self.key_permit_repo.set_rules_for_key_user(key_id, tunnel_user_id, rules_by_user[tunnel_user_id])
        self.auth_keys_service.regenerate(tunnel_user_id)

    def toggle_key(self, key_id: int, enabled: bool) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        self.key_repo.set_enabled(key, enabled=enabled)
        user_ids = self.assignment_repo.list_user_ids_for_key(key_id)
        self.auth_keys_service.regenerate_many(user_ids)

    def delete_key(self, key_id: int) -> None:
        self._assert_write_allowed()
        key = self.key_repo.get(key_id)
        if not key:
            raise NotFoundError("SSH key not found.")
        user_ids = self.assignment_repo.list_user_ids_for_key(key_id)
        self.key_repo.delete(key)
        self.auth_keys_service.regenerate_many(user_ids)

    def add_permit_rule(self, tunnel_user_id: int, payload: PermitOpenCreate):
        self._assert_write_allowed()
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")
        try:
            return self.rule_repo.create(
                tunnel_user_id=tunnel_user_id,
                alias=payload.alias,
                host=payload.host,
                port=payload.port,
                comment=payload.comment,
                enabled=payload.enabled,
            )
        except IntegrityError as exc:
            raise ValidationError("PermitOpen rule with this host:port already exists for this user.") from exc

    def toggle_rule(self, rule_id: int, enabled: bool) -> None:
        self._assert_write_allowed()
        rule = self.rule_repo.get(rule_id)
        if not rule:
            raise NotFoundError("PermitOpen rule not found.")
        self.rule_repo.set_enabled(rule, enabled=enabled)
        user_ids = self.assignment_repo.list_user_ids_for_rule(rule_id)
        self.auth_keys_service.regenerate_many(user_ids)

    def delete_rule(self, rule_id: int) -> None:
        self._assert_write_allowed()
        rule = self.rule_repo.get(rule_id)
        if not rule:
            raise NotFoundError("PermitOpen rule not found.")
        tunnel_user_id = rule.tunnel_user_id
        user_ids = self.assignment_repo.list_user_ids_for_rule(rule_id)
        self.rule_repo.delete(rule)
        affected = sorted(set(user_ids) | {tunnel_user_id})
        self.auth_keys_service.regenerate_many(affected)

    def regenerate(self, tunnel_user_id: int) -> None:
        self._assert_write_allowed()
        self.auth_keys_service.regenerate(tunnel_user_id)
