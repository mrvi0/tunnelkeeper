from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from pydantic import BaseModel, Field, ValidationInfo, field_validator

USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9.-]+(?<!-)$")

SHELL_CHOICES = {
    "nologin": "/usr/sbin/nologin",
    "false": "/bin/false",
    "bash": "/bin/bash",
    "sh": "/bin/sh",
}


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
    linux_shell: str = Field(default="/usr/sbin/nologin")
    supplementary_groups: str = Field(default="", max_length=500)
    allow_tcp_forwarding: bool = True
    permit_tty: bool = False
    x11_forwarding: bool = False
    allow_agent_forwarding: bool = False
    force_command: str = Field(default='echo "Tunnel only";exit')
    tunnel_only: bool = True
    destination_ids: list[int] = Field(default_factory=list)

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

    @field_validator("linux_shell")
    @classmethod
    def _shell(cls, value: str) -> str:
        if value in SHELL_CHOICES.values():
            return value
        if value in SHELL_CHOICES:
            return SHELL_CHOICES[value]
        if value.startswith("/"):
            return value
        raise ValueError("Invalid shell.")


class TunnelUserUpdate(BaseModel):
    comment: str = Field(default="", max_length=255)
    linux_shell: str = Field(default="/usr/sbin/nologin")
    supplementary_groups: str = Field(default="", max_length=500)
    allow_tcp_forwarding: bool = True
    permit_tty: bool = False
    x11_forwarding: bool = False
    allow_agent_forwarding: bool = False
    force_command: str = Field(default="")
    tunnel_only: bool = False
    destination_ids: list[int] = Field(default_factory=list)

    @field_validator("linux_shell")
    @classmethod
    def _shell(cls, value: str) -> str:
        if value in SHELL_CHOICES.values():
            return value
        if value in SHELL_CHOICES:
            return SHELL_CHOICES[value]
        if value.startswith("/"):
            return value
        raise ValueError("Invalid shell.")


class DestinationCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    comment: str = Field(default="", max_length=255)
    enabled: bool = True

    @field_validator("host")
    @classmethod
    def _host(cls, value: str) -> str:
        return validate_host(value)


class SSHKeyCreate(BaseModel):
    tunnel_user_id: int
    name: str = Field(min_length=1, max_length=100)
    public_key: str = Field(min_length=20)
    enabled: bool = True
