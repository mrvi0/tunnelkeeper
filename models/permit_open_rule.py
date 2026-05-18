from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class PermitOpenRule(Base):
    __tablename__ = "permit_open_rules"
    __table_args__ = (UniqueConstraint("tunnel_user_id", "host", "port", name="uq_user_host_port"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tunnel_user_id: Mapped[int] = mapped_column(ForeignKey("tunnel_users.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tunnel_user = relationship("TunnelUser", back_populates="permit_open_rules")
