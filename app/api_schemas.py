from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import DestinationCreate, SSHKeyCreate, TunnelUserCreate, TunnelUserUpdate, validate_host


class DestinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    host: str
    port: int
    comment: str
    enabled: bool
    created_at: datetime


class DestinationPatch(BaseModel):
    alias: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    comment: str | None = None
    enabled: bool | None = None

    @field_validator("host")
    @classmethod
    def _host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_host(value)


class SSHKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tunnel_user_id: int
    name: str
    public_key: str
    fingerprint: str
    enabled: bool
    created_at: datetime


class TunnelUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    comment: str
    linux_home: str
    linux_shell: str
    supplementary_groups: str
    allow_tcp_forwarding: bool
    permit_tty: bool
    x11_forwarding: bool
    allow_agent_forwarding: bool
    force_command: str
    created_at: datetime
    destination_ids: list[int] = Field(default_factory=list)
    sshd_config_path: str = ""


class TunnelUserDetailOut(TunnelUserOut):
    keys: list[SSHKeyOut] = Field(default_factory=list)
    destinations: list[DestinationOut] = Field(default_factory=list)


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str
    action: str
    target: str
    details: str
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    readonly_mode: bool
    enable_web_ui: bool
    enable_api: bool
    sshd_warning: str | None = None


class MessageOut(BaseModel):
    message: str


class ErrorOut(BaseModel):
    detail: str


# Re-export request bodies shared with service layer
DestinationCreateIn = DestinationCreate
TunnelUserCreateIn = TunnelUserCreate
TunnelUserUpdateIn = TunnelUserUpdate
SSHKeyCreateIn = SSHKeyCreate


class SSHKeyCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    public_key: str = Field(min_length=20)
    enabled: bool = True


class EnabledPatch(BaseModel):
    enabled: bool
