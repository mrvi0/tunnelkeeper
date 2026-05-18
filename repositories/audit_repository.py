from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, actor: str, action: str, target: str, details: str) -> AuditLog:
        entity = AuditLog(actor=actor, action=action, target=target, details=details)
        self.db.add(entity)
        self.db.flush()
        return entity

    def latest(self, limit: int = 20) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())
