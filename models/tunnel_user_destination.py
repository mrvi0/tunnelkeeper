from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TunnelUserDestination(Base):
    __tablename__ = "tunnel_user_destinations"

    tunnel_user_id: Mapped[int] = mapped_column(
        ForeignKey("tunnel_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tunnel_destination_id: Mapped[int] = mapped_column(
        ForeignKey("tunnel_destinations.id", ondelete="CASCADE"),
        primary_key=True,
    )
