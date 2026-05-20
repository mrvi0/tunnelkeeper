from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from pydantic import BaseModel, Field, ValidationInfo, field_validator

USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9.-]+(?<!-)$")


def validate_username(username: str) -> str:
    if not USERNAME_RE.match(username):
        raise ValueError("Username must match Linux-compatible pattern.")
    return username


def validate_host(host: str) -> str:
    host = host.strip()
    if not host:
        raise ValueError("Host is required.")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        if not HOST_RE.match(host) or ".." in host:
            raise ValueError("Host must be valid IP or hostname.")
    return host


class TunnelUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    comment: str = Field(default="", max_length=255)
    linux_home: str = Field(default="")

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        return validate_username(value)

    @field_validator("linux_home")
    @classmethod
    def _home(cls, value: str, info: ValidationInfo) -> str:
        if value:
            return str(Path(value).expanduser())
        username = info.data.get("username", "")
        return f"/home/{username}"


class TunnelUserUpdate(BaseModel):
    comment: str = Field(default="", max_length=255)


class SSHKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    public_key: str = Field(min_length=20)
    enabled: bool = True


class PermitOpenCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    comment: str = Field(default="", max_length=255)
    enabled: bool = True

    @field_validator("host")
    @classmethod
    def _host(cls, value: str) -> str:
        return validate_host(value)
