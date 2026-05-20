from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from generators.authorized_keys_generator import render_authorized_keys_for_user
from repositories.key_permit_repository import KeyPermitRepository
from repositories.ssh_key_repository import SSHKeyRepository
from repositories.tunnel_user_repository import TunnelUserRepository
from services.exceptions import NotFoundError
from services.linux_service import LinuxService

logger = logging.getLogger(__name__)


class AuthorizedKeysService:
    def __init__(self, db: Session, linux_service: LinuxService | None = None) -> None:
        self.db = db
        self.user_repo = TunnelUserRepository(db)
        self.key_repo = SSHKeyRepository(db)
        self.key_permit_repo = KeyPermitRepository(db)
        self.linux_service = linux_service or LinuxService()

    def regenerate(self, tunnel_user_id: int) -> None:
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")

        _, auth_keys_path = self.linux_service.ensure_ssh_directory(user)
        keys = self.key_repo.list_by_user(user.id)
        rules_by_key = {
            key.id: self.key_permit_repo.list_rules_for_key_user(key.id, tunnel_user_id)
            for key in keys
        }
        output = render_authorized_keys_for_user(keys, tunnel_user_id, rules_by_key)

        backup_path = self.linux_service.backup_file(auth_keys_path)
        self.linux_service.atomic_write(auth_keys_path, output)
        logger.info(
            "Regenerated authorized_keys for user=%s keys=%s backup=%s",
            user.username,
            len(keys),
            backup_path,
        )

    def regenerate_many(self, tunnel_user_ids: list[int]) -> None:
        for tunnel_user_id in sorted(set(tunnel_user_ids)):
            self.regenerate(tunnel_user_id)
