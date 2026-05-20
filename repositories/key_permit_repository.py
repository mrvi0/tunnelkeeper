from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.permit_open_rule import PermitOpenRule
from models.ssh_key_permit_rule import SSHKeyPermitRule


class KeyPermitRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_rule_ids_for_key_user(self, ssh_key_id: int, tunnel_user_id: int) -> list[int]:
        stmt = select(SSHKeyPermitRule.permit_open_rule_id).where(
            SSHKeyPermitRule.ssh_key_id == ssh_key_id,
            SSHKeyPermitRule.tunnel_user_id == tunnel_user_id,
        )
        return list(self.db.scalars(stmt).all())

    def list_rules_for_key_user(self, ssh_key_id: int, tunnel_user_id: int) -> list[PermitOpenRule]:
        stmt = (
            select(PermitOpenRule)
            .join(SSHKeyPermitRule, SSHKeyPermitRule.permit_open_rule_id == PermitOpenRule.id)
            .where(
                SSHKeyPermitRule.ssh_key_id == ssh_key_id,
                SSHKeyPermitRule.tunnel_user_id == tunnel_user_id,
            )
            .order_by(PermitOpenRule.alias)
        )
        return list(self.db.scalars(stmt).all())

    def set_rules_for_key_user(self, ssh_key_id: int, tunnel_user_id: int, rule_ids: list[int]) -> None:
        self.db.execute(
            delete(SSHKeyPermitRule).where(
                SSHKeyPermitRule.ssh_key_id == ssh_key_id,
                SSHKeyPermitRule.tunnel_user_id == tunnel_user_id,
            )
        )
        for rule_id in sorted(set(rule_ids)):
            self.db.add(
                SSHKeyPermitRule(
                    ssh_key_id=ssh_key_id,
                    tunnel_user_id=tunnel_user_id,
                    permit_open_rule_id=rule_id,
                )
            )
        self.db.flush()

    def delete_all_for_key_user(self, ssh_key_id: int, tunnel_user_id: int) -> None:
        self.db.execute(
            delete(SSHKeyPermitRule).where(
                SSHKeyPermitRule.ssh_key_id == ssh_key_id,
                SSHKeyPermitRule.tunnel_user_id == tunnel_user_id,
            )
        )
        self.db.flush()
