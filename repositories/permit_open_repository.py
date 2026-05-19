from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.permit_open_rule import PermitOpenRule


class PermitOpenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, tunnel_user_id: int) -> list[PermitOpenRule]:
        stmt = (
            select(PermitOpenRule)
            .where(PermitOpenRule.tunnel_user_id == tunnel_user_id)
            .order_by(PermitOpenRule.alias, PermitOpenRule.host)
        )
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        return len(self.db.scalars(select(PermitOpenRule.id)).all())

    def get(self, rule_id: int) -> PermitOpenRule | None:
        return self.db.get(PermitOpenRule, rule_id)

    def create(
        self,
        *,
        tunnel_user_id: int,
        alias: str,
        host: str,
        port: int,
        comment: str,
        enabled: bool,
    ) -> PermitOpenRule:
        entity = PermitOpenRule(
            tunnel_user_id=tunnel_user_id,
            alias=alias,
            host=host,
            port=port,
            comment=comment,
            enabled=enabled,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def set_enabled(self, entity: PermitOpenRule, enabled: bool) -> PermitOpenRule:
        entity.enabled = enabled
        self.db.flush()
        return entity

    def delete(self, entity: PermitOpenRule) -> None:
        self.db.delete(entity)
        self.db.flush()
