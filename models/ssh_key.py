from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class SSHKey(Base):
    __tablename__ = "ssh_keys"
    __table_args__ = (UniqueConstraint("public_key", name="uq_public_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user_assignments = relationship(
        "SSHKeyUserAssignment",
        back_populates="ssh_key",
        cascade="all, delete-orphan",
    )
    tunnel_users = relationship(
        "TunnelUser",
        secondary="ssh_key_user_assignments",
        back_populates="ssh_keys",
        viewonly=True,
    )
