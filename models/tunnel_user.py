from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class TunnelUser(Base):
    __tablename__ = "tunnel_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    linux_home: Mapped[str] = mapped_column(String(255), nullable=False)
    linux_shell: Mapped[str] = mapped_column(String(255), default="/usr/sbin/nologin", nullable=False)
    supplementary_groups: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    allow_tcp_forwarding: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    permit_tty: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    x11_forwarding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_agent_forwarding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    force_command: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ssh_keys = relationship("SSHKey", back_populates="tunnel_user", cascade="all, delete-orphan")
    destinations = relationship(
        "TunnelDestination",
        secondary="tunnel_user_destinations",
        back_populates="tunnel_users",
    )

    @property
    def sshd_config_filename(self) -> str:
        return f"{self.username}.conf"

    @property
    def allows_interactive_login(self) -> bool:
        return not self.force_command.strip() and self.linux_shell not in (
            "/usr/sbin/nologin",
            "/bin/false",
            "/sbin/nologin",
        )
