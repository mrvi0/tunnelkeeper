from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def _extract_token(*, authorization: str | None, x_api_key: str | None) -> str | None:
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    return None


def _token_matches(provided: str, expected: str) -> bool:
    if len(provided) != len(expected):
        return False
    return secrets.compare_digest(provided, expected)


def require_api_token(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str]:
    settings = get_settings()
    provided = _extract_token(authorization=authorization, x_api_key=x_api_key)
    expected = settings.api_token
    if not provided or not _token_matches(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token. Use Authorization: Bearer <API_TOKEN> or X-API-Key.",
        )
    return {"actor": "api"}
