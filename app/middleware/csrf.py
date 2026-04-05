import hashlib
import secrets
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.middleware.auth import SECRET_KEY

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_TOKEN_LENGTH = 48


def generate_csrf_token() -> str:
    raw = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
    signature = hashlib.sha256(f"{raw}:{SECRET_KEY}".encode("utf-8")).hexdigest()
    return f"{raw}.{signature}"


def verify_csrf_token(token: str) -> bool:
    if not token or "." not in token:
        return False

    raw, signature = token.rsplit(".", 1)
    expected = hashlib.sha256(f"{raw}:{SECRET_KEY}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(signature, expected)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path.startswith("/health"):
            return await call_next(request)

        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            existing = request.cookies.get(CSRF_COOKIE_NAME)
            if not existing or not verify_csrf_token(existing):
                csrf_token = generate_csrf_token()
                response.set_cookie(
                    key=CSRF_COOKIE_NAME,
                    value=csrf_token,
                    httponly=False,
                    secure=False,
                    samesite="lax",
                    max_age=86400 * 30,
                    path="/",
                )
            return response

        csrf_token = request.headers.get(CSRF_HEADER_NAME) or request.query_params.get(
            CSRF_FORM_FIELD
        )

        if not csrf_token and request.method in ("POST", "PUT", "DELETE", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                form = await request.form()
                csrf_token = form.get(CSRF_FORM_FIELD)
                request._form = form

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

        if not csrf_token or not cookie_token:
            return HTMLResponse("CSRF token missing", status_code=403)

        if not verify_csrf_token(csrf_token) or not verify_csrf_token(cookie_token):
            return HTMLResponse("Invalid CSRF token", status_code=403)

        if csrf_token != cookie_token:
            return HTMLResponse("CSRF token mismatch", status_code=403)

        return await call_next(request)


def get_csrf_token(request: Request) -> str:
    token = request.cookies.get(CSRF_COOKIE_NAME, "")
    if not token or not verify_csrf_token(token):
        return generate_csrf_token()
    return token
