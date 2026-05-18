from __future__ import annotations

import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import ensure_csrf, get_client_ip, runtime_auth_state, validate_csrf

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login")
def login_page(request: Request):
    csrf_token = ensure_csrf(request)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "csrf_token": csrf_token,
            "error": None,
            "expired": bool(request.query_params.get("expired")),
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf(request, csrf_token)
    client_ip = get_client_ip(request)
    runtime_auth_state.rate_limiter.check_or_raise(client_ip)
    if not runtime_auth_state.authenticate(username, password):
        runtime_auth_state.rate_limiter.register_failure(client_ip)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": ensure_csrf(request),
                "error": "Invalid credentials",
                "expired": False,
            },
            status_code=401,
        )
    runtime_auth_state.rate_limiter.reset(client_ip)
    request.session["admin_user"] = {"username": username, "login_at": int(time.time())}
    request.session["last_seen"] = int(time.time())
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
