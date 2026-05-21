from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.tunnel_user import TunnelUser


class TunnelUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[TunnelUser]:
        stmt = (
            select(TunnelUser)
            .options(selectinload(TunnelUser.destinations), selectinload(TunnelUser.ssh_keys))
            .order_by(TunnelUser.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get(self, user_id: int) -> TunnelUser | None:
        stmt = (
            select(TunnelUser)
            .options(selectinload(TunnelUser.destinations), selectinload(TunnelUser.ssh_keys))
            .where(TunnelUser.id == user_id)
        )
        return self.db.scalar(stmt)

    def get_by_username(self, username: str) -> TunnelUser | None:
        stmt = select(TunnelUser).where(TunnelUser.username == username)
        return self.db.scalar(stmt)

    def create(self, *, username: str, comment: str, linux_home: str, **kwargs) -> TunnelUser:
        entity = TunnelUser(username=username, comment=comment, linux_home=linux_home, **kwargs)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: TunnelUser, **kwargs) -> TunnelUser:
        for key, value in kwargs.items():
            setattr(entity, key, value)
        self.db.flush()
        return entity

    def delete(self, entity: TunnelUser) -> None:
        self.db.delete(entity)
        self.db.flush()
