from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from generators.authorized_keys_generator import render_authorized_keys
from generators.sshd_config_generator import render_user_sshd_config
from repositories.destination_repository import DestinationRepository
from repositories.ssh_key_repository import SSHKeyRepository
from repositories.tunnel_user_repository import TunnelUserRepository
from repositories.user_destination_repository import UserDestinationRepository
from services.exceptions import NotFoundError
from services.linux_service import LinuxService

logger = logging.getLogger(__name__)


class UserProvisionService:
    def __init__(self, db: Session, linux_service: LinuxService | None = None) -> None:
        self.db = db
        self.user_repo = TunnelUserRepository(db)
        self.key_repo = SSHKeyRepository(db)
        self.dest_repo = DestinationRepository(db)
        self.user_dest_repo = UserDestinationRepository(db)
        self.linux_service = linux_service or LinuxService()

    def provision_user(self, tunnel_user_id: int, *, reload_sshd: bool = True) -> None:
        user = self.user_repo.get(tunnel_user_id)
        if not user:
            raise NotFoundError("Tunnel user not found.")

        keys = self.key_repo.list_by_user(user.id)
        destinations = self.user_dest_repo.list_destinations_for_user(user.id)

        _, auth_keys_path = self.linux_service.ensure_ssh_directory(user)
        auth_content = render_authorized_keys(keys)
        auth_backup = self.linux_service.backup_file(auth_keys_path)
        self.linux_service.atomic_write(auth_keys_path, auth_content, mode=0o600)
        self.linux_service._chown_tree(auth_keys_path.parent.parent, user.username)

        sshd_path = self.linux_service.sshd_config_path(user)
        sshd_content = render_user_sshd_config(user, destinations)
        sshd_backup = self.linux_service.backup_file(sshd_path)
        self.linux_service.atomic_write(sshd_path, sshd_content, mode=0o644)

        logger.info(
            "Provisioned user=%s keys=%s destinations=%s auth_backup=%s sshd_backup=%s",
            user.username,
            len(keys),
            len(destinations),
            auth_backup,
            sshd_backup,
        )

        if reload_sshd:
            self.linux_service.reload_sshd()

    def provision_all_users(self, *, reload_sshd: bool = True) -> None:
        users = self.user_repo.list()
        for user in users:
            self.provision_user(user.id, reload_sshd=False)
        if reload_sshd and users:
            self.linux_service.reload_sshd()
