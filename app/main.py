from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.logging_setup import configure_logging
from app.security import runtime_auth_state
from routers.api_v1 import router as api_v1_router
from routers.auth import router as auth_router
from routers.web import router as web_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path("database").mkdir(parents=True, exist_ok=True)
    print("================================================")
    print("TunnelKeeper")
    print("================================================")
    host = settings.app_host
    port = settings.app_port
    print(f"Bind:     http://{host}:{port}")
    if host in ("0.0.0.0", "::", "[::]"):
        print(f"Remote:   http://<server-ip>:{port}")

    if settings.enable_web_ui:
        creds = runtime_auth_state.bootstrap_credentials()
        print("Web UI:   enabled")
        print(f"Login:    {creds.username}")
        print(f"Password: {creds.plain_password}")
    else:
        print("Web UI:   disabled (ENABLE_WEB_UI=false)")

    if settings.enable_api:
        print("API:      enabled at /api/v1 (Bearer token from API_TOKEN)")
        print(f"Docs:     http://{host}:{port}/docs")
    else:
        print("API:      disabled (set ENABLE_API=true and API_TOKEN=...)")

    print("================================================")
    logger.info(
        "Started web_ui=%s api=%s readonly=%s",
        settings.enable_web_ui,
        settings.enable_api,
        settings.readonly_mode,
    )
    yield


app = FastAPI(
    title="TunnelKeeper",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api else None,
    redoc_url="/redoc" if settings.enable_api else None,
    openapi_url="/openapi.json" if settings.enable_api else None,
)

if settings.enable_web_ui:
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        max_age=settings.session_max_idle_seconds,
        same_site="lax",
        https_only=settings.secure_cookies,
    )
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(auth_router)
    app.include_router(web_router)

if settings.enable_api:
    app.include_router(api_v1_router)


@app.get("/")
def root():
    payload = {
        "service": "TunnelKeeper",
        "web_ui": settings.enable_web_ui,
        "api": settings.enable_api,
    }
    if settings.enable_api:
        payload["api_base"] = "/api/v1"
        payload["health"] = "/api/v1/health"
    if not settings.enable_web_ui and settings.enable_api:
        return JSONResponse(payload)
    if settings.enable_web_ui:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse(payload)
