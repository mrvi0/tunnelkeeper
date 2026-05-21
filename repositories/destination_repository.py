from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.tunnel_destination import TunnelDestination


class DestinationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[TunnelDestination]:
        stmt = select(TunnelDestination).order_by(TunnelDestination.alias, TunnelDestination.host)
        return list(self.db.scalars(stmt).all())

    def list_enabled(self) -> list[TunnelDestination]:
        stmt = (
            select(TunnelDestination)
            .where(TunnelDestination.enabled.is_(True))
            .order_by(TunnelDestination.alias)
        )
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        return len(self.db.scalars(select(TunnelDestination.id)).all())

    def get(self, destination_id: int) -> TunnelDestination | None:
        return self.db.get(TunnelDestination, destination_id)

    def create(
        self,
        *,
        alias: str,
        host: str,
        port: int,
        comment: str,
        enabled: bool,
    ) -> TunnelDestination:
        entity = TunnelDestination(alias=alias, host=host, port=port, comment=comment, enabled=enabled)
        self.db.add(entity)
        self.db.flush()
        return entity

    def set_enabled(self, entity: TunnelDestination, enabled: bool) -> TunnelDestination:
        entity.enabled = enabled
        self.db.flush()
        return entity

    def delete(self, entity: TunnelDestination) -> None:
        self.db.delete(entity)
        self.db.flush()
