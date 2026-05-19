from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.ssh_key import SSHKey


class SSHKeyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[SSHKey]:
        stmt = (
            select(SSHKey)
            .options(selectinload(SSHKey.tunnel_user), selectinload(SSHKey.permit_rules))
            .order_by(SSHKey.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def list_by_user(self, tunnel_user_id: int) -> list[SSHKey]:
        stmt = (
            select(SSHKey)
            .options(selectinload(SSHKey.permit_rules))
            .where(SSHKey.tunnel_user_id == tunnel_user_id)
            .order_by(SSHKey.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def count(self) -> int:
        return len(self.db.scalars(select(SSHKey.id)).all())

    def get(self, key_id: int) -> SSHKey | None:
        stmt = (
            select(SSHKey)
            .options(
                selectinload(SSHKey.tunnel_user),
                selectinload(SSHKey.permit_rules),
            )
            .where(SSHKey.id == key_id)
        )
        return self.db.scalar(stmt)

    def create(
        self,
        *,
        tunnel_user_id: int,
        name: str,
        public_key: str,
        fingerprint: str,
        enabled: bool,
    ) -> SSHKey:
        entity = SSHKey(
            tunnel_user_id=tunnel_user_id,
            name=name,
            public_key=public_key,
            fingerprint=fingerprint,
            enabled=enabled,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def set_enabled(self, entity: SSHKey, enabled: bool) -> SSHKey:
        entity.enabled = enabled
        self.db.flush()
        return entity

    def delete(self, entity: SSHKey) -> None:
        self.db.delete(entity)
        self.db.flush()
