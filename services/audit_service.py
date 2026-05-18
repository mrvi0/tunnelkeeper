from __future__ import annotations

from sqlalchemy.orm import Session

from repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, db: Session) -> None:
        self.repo = AuditRepository(db)

    def log(self, *, actor: str, action: str, target: str, details: str) -> None:
        self.repo.create(actor=actor, action=action, target=target, details=details)

    def latest(self, limit: int = 20):
        return self.repo.latest(limit=limit)
