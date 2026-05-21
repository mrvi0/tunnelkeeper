from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class TunnelDestination(Base):
    """Global PermitOpen catalog (host:port). Applied per user via sshd Match User."""

    __tablename__ = "tunnel_destinations"
    __table_args__ = (UniqueConstraint("host", "port", name="uq_destination_host_port"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tunnel_users = relationship(
        "TunnelUser",
        secondary="tunnel_user_destinations",
        back_populates="destinations",
    )
