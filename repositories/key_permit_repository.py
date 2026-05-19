from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.permit_open_rule import PermitOpenRule
from models.ssh_key_permit_rule import SSHKeyPermitRule


class KeyPermitRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_rule_ids_for_key(self, ssh_key_id: int) -> list[int]:
        stmt = select(SSHKeyPermitRule.permit_open_rule_id).where(SSHKeyPermitRule.ssh_key_id == ssh_key_id)
        return list(self.db.scalars(stmt).all())

    def list_rules_for_key(self, ssh_key_id: int) -> list[PermitOpenRule]:
        stmt = (
            select(PermitOpenRule)
            .join(SSHKeyPermitRule, SSHKeyPermitRule.permit_open_rule_id == PermitOpenRule.id)
            .where(SSHKeyPermitRule.ssh_key_id == ssh_key_id)
            .order_by(PermitOpenRule.alias)
        )
        return list(self.db.scalars(stmt).all())

    def set_rules_for_key(self, ssh_key_id: int, rule_ids: list[int]) -> None:
        self.db.execute(delete(SSHKeyPermitRule).where(SSHKeyPermitRule.ssh_key_id == ssh_key_id))
        for rule_id in sorted(set(rule_ids)):
            self.db.add(SSHKeyPermitRule(ssh_key_id=ssh_key_id, permit_open_rule_id=rule_id))
        self.db.flush()

    def list_user_ids_for_rule(self, rule_id: int) -> list[int]:
        from models.ssh_key import SSHKey

        stmt = (
            select(SSHKey.tunnel_user_id)
            .join(SSHKeyPermitRule, SSHKeyPermitRule.ssh_key_id == SSHKey.id)
            .where(SSHKeyPermitRule.permit_open_rule_id == rule_id)
            .distinct()
        )
        return list(self.db.scalars(stmt).all())
