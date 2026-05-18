from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from generators.authorized_keys_generator import render_authorized_keys
from repositories.permit_open_repository import PermitOpenRepository
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
        self.rule_repo = PermitOpenRepository(db)
        self.linux_service = linux_service or LinuxService()

    def regenerate(self, tunnel_user_id: int) -> None:
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")

        _, auth_keys_path = self.linux_service.ensure_ssh_directory(user)
        keys = self.key_repo.list_by_user(user.id)
        rules = self.rule_repo.list_by_user(user.id)
        output = render_authorized_keys(keys, rules)

        backup_path = self.linux_service.backup_file(auth_keys_path)
        self.linux_service.atomic_write(auth_keys_path, output)
        logger.info(
            "Regenerated authorized_keys for user=%s backup=%s",
            user.username,
            backup_path,
        )
