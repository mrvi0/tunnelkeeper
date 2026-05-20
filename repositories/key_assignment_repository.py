from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.ssh_key_user_assignment import SSHKeyUserAssignment
from models.tunnel_user import TunnelUser


class KeyAssignmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_user_ids_for_key(self, ssh_key_id: int) -> list[int]:
        stmt = select(SSHKeyUserAssignment.tunnel_user_id).where(SSHKeyUserAssignment.ssh_key_id == ssh_key_id)
        return list(self.db.scalars(stmt).all())

    def list_users_for_key(self, ssh_key_id: int) -> list[TunnelUser]:
        stmt = (
            select(TunnelUser)
            .join(SSHKeyUserAssignment, SSHKeyUserAssignment.tunnel_user_id == TunnelUser.id)
            .where(SSHKeyUserAssignment.ssh_key_id == ssh_key_id)
            .order_by(TunnelUser.username)
        )
        return list(self.db.scalars(stmt).all())

    def set_users_for_key(self, ssh_key_id: int, tunnel_user_ids: list[int]) -> None:
        self.db.execute(delete(SSHKeyUserAssignment).where(SSHKeyUserAssignment.ssh_key_id == ssh_key_id))
        for user_id in sorted(set(tunnel_user_ids)):
            self.db.add(SSHKeyUserAssignment(ssh_key_id=ssh_key_id, tunnel_user_id=user_id))
        self.db.flush()

    def add_users_for_key(self, ssh_key_id: int, tunnel_user_ids: list[int]) -> None:
        existing = set(self.list_user_ids_for_key(ssh_key_id))
        for user_id in sorted(set(tunnel_user_ids)):
            if user_id not in existing:
                self.db.add(SSHKeyUserAssignment(ssh_key_id=ssh_key_id, tunnel_user_id=user_id))
        self.db.flush()

    def list_key_ids_for_user(self, tunnel_user_id: int) -> list[int]:
        stmt = select(SSHKeyUserAssignment.ssh_key_id).where(
            SSHKeyUserAssignment.tunnel_user_id == tunnel_user_id
        )
        return list(self.db.scalars(stmt).all())

    def list_user_ids_for_rule(self, rule_id: int) -> list[int]:
        from models.ssh_key_permit_rule import SSHKeyPermitRule

        stmt = (
            select(SSHKeyUserAssignment.tunnel_user_id)
            .join(
                SSHKeyPermitRule,
                (SSHKeyPermitRule.ssh_key_id == SSHKeyUserAssignment.ssh_key_id)
                & (SSHKeyPermitRule.tunnel_user_id == SSHKeyUserAssignment.tunnel_user_id),
            )
            .where(SSHKeyPermitRule.permit_open_rule_id == rule_id)
            .distinct()
        )
        return list(self.db.scalars(stmt).all())
