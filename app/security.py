from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

import bcrypt
from fastapi import HTTPException, Request, status

from app.config import get_settings

SUPPORTED_KEY_TYPES = {"ssh-ed25519", "ssh-rsa"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


@dataclass
class RuntimeAdminCredentials:
    username: str
    password_hash: str
    plain_password: str
    created_at: float = field(default_factory=time.time)


@dataclass
class LoginRateLimiter:
    attempts_by_ip: dict[str, list[float]] = field(default_factory=dict)

    def check_or_raise(self, client_ip: str) -> None:
        settings = get_settings()
        now = time.time()
        attempts = self.attempts_by_ip.get(client_ip, [])
        threshold = now - settings.login_rate_limit_window_seconds
        attempts = [x for x in attempts if x >= threshold]
        if len(attempts) >= settings.login_rate_limit_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
            )
        self.attempts_by_ip[client_ip] = attempts

    def register_failure(self, client_ip: str) -> None:
        now = time.time()
        self.attempts_by_ip.setdefault(client_ip, []).append(now)

    def reset(self, client_ip: str) -> None:
        self.attempts_by_ip.pop(client_ip, None)


class RuntimeAuthState:
    def __init__(self) -> None:
        self._credentials: RuntimeAdminCredentials | None = None
        self.rate_limiter = LoginRateLimiter()

    def bootstrap_credentials(self) -> RuntimeAdminCredentials:
        username = f"admin_{secrets.token_urlsafe(5)}"
        password = secrets.token_urlsafe(12)
        credentials = RuntimeAdminCredentials(
            username=username,
            password_hash=hash_password(password),
            plain_password=password,
        )
        self._credentials = credentials
        return credentials

    @property
    def credentials(self) -> RuntimeAdminCredentials:
        if self._credentials is None:
            raise RuntimeError("Runtime credentials are not initialized.")
        return self._credentials

    def authenticate(self, username: str, password: str) -> bool:
        current = self.credentials
        return username == current.username and verify_password(password, current.password_hash)


runtime_auth_state = RuntimeAuthState()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def ensure_csrf(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return str(token)


def validate_csrf(request: Request, submitted_token: str | None) -> None:
    session_token = request.session.get("csrf_token")
    if not submitted_token or not session_token or submitted_token != session_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token.")


def parse_public_key(public_key: str) -> tuple[str, bytes]:
    chunks = public_key.strip().split()
    if len(chunks) < 2:
        raise ValueError("Public key must include key type and key material.")
    key_type, key_b64 = chunks[0], chunks[1]
    if key_type not in SUPPORTED_KEY_TYPES:
        raise ValueError("Only ssh-ed25519 and ssh-rsa are supported.")
    try:
        key_bytes = base64.b64decode(key_b64.encode("utf-8"), validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid SSH key base64 payload.") from exc
    return key_type, key_bytes


def fingerprint_ssh_key(public_key: str) -> str:
    _, key_bytes = parse_public_key(public_key)
    digest = hashlib.sha256(key_bytes).digest()
    value = base64.b64encode(digest).decode("utf-8").rstrip("=")
    return f"SHA256:{value}"


def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def safe_session_user(request: Request) -> dict[str, Any] | None:
    data = request.session.get("admin_user")
    if not isinstance(data, dict):
        return None
    return data
