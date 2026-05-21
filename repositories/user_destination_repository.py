from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.tunnel_destination import TunnelDestination
from models.tunnel_user_destination import TunnelUserDestination


class UserDestinationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_destination_ids(self, tunnel_user_id: int) -> list[int]:
        stmt = select(TunnelUserDestination.tunnel_destination_id).where(
            TunnelUserDestination.tunnel_user_id == tunnel_user_id
        )
        return list(self.db.scalars(stmt).all())

    def list_destinations_for_user(self, tunnel_user_id: int) -> list[TunnelDestination]:
        stmt = (
            select(TunnelDestination)
            .join(
                TunnelUserDestination,
                TunnelUserDestination.tunnel_destination_id == TunnelDestination.id,
            )
            .where(TunnelUserDestination.tunnel_user_id == tunnel_user_id)
            .order_by(TunnelDestination.alias)
        )
        return list(self.db.scalars(stmt).all())

    def set_destinations_for_user(self, tunnel_user_id: int, destination_ids: list[int]) -> None:
        self.db.execute(
            delete(TunnelUserDestination).where(TunnelUserDestination.tunnel_user_id == tunnel_user_id)
        )
        for dest_id in sorted(set(destination_ids)):
            self.db.add(
                TunnelUserDestination(tunnel_user_id=tunnel_user_id, tunnel_destination_id=dest_id)
            )
        self.db.flush()

    def list_user_ids_for_destination(self, destination_id: int) -> list[int]:
        stmt = select(TunnelUserDestination.tunnel_user_id).where(
            TunnelUserDestination.tunnel_destination_id == destination_id
        )
        return list(self.db.scalars(stmt).all())
