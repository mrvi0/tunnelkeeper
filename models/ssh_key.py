from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class SSHKey(Base):
    __tablename__ = "ssh_keys"
    __table_args__ = (UniqueConstraint("public_key", name="uq_public_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tunnel_user_id: Mapped[int] = mapped_column(ForeignKey("tunnel_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tunnel_user = relationship("TunnelUser", back_populates="ssh_keys")
    permit_rules = relationship(
        "PermitOpenRule",
        secondary="ssh_key_permit_rules",
        back_populates="ssh_keys",
    )
