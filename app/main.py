from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.logging_setup import configure_logging
from app.security import runtime_auth_state
from routers.auth import router as auth_router
from routers.web import router as web_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path("database").mkdir(parents=True, exist_ok=True)
    creds = runtime_auth_state.bootstrap_credentials()
    print("================================================")
    print("TunnelKeeper Admin Panel")
    print("================================================")
    print(f"URL:      http://{settings.app_host}:{settings.app_port}")
    print(f"Login:    {creds.username}")
    print(f"Password: {creds.plain_password}")
    print("================================================")
    logger.info("Runtime admin credentials generated.")
    yield


app = FastAPI(title="TunnelKeeper", lifespan=lifespan)
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
