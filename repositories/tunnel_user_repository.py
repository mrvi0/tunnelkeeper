from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.tunnel_user import TunnelUser


class TunnelUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[TunnelUser]:
        stmt = select(TunnelUser).order_by(TunnelUser.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get(self, user_id: int) -> TunnelUser | None:
        return self.db.get(TunnelUser, user_id)

    def get_by_username(self, username: str) -> TunnelUser | None:
        stmt = select(TunnelUser).where(TunnelUser.username == username)
        return self.db.scalar(stmt)

    def create(self, *, username: str, comment: str, linux_home: str) -> TunnelUser:
        entity = TunnelUser(username=username, comment=comment, linux_home=linux_home)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update_comment(self, entity: TunnelUser, comment: str) -> TunnelUser:
        entity.comment = comment
        self.db.flush()
        return entity

    def delete(self, entity: TunnelUser) -> None:
        self.db.delete(entity)
        self.db.flush()
