import os
import uuid
import hashlib
import secrets
import functools
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable

from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "careloop-demo-secret-key-change-in-production")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
SESSION_DURATION_HOURS = 24
PASSWORD_SALT = "careloop-salt-v1"

VALID_ROLES = {
    "patient",
    "provider",
    "caregiver",
    "specialist",
    "nurse",
    "coordinator",
    "admin",
}

ROLE_PERMISSIONS = {
    "admin": {"all"},
    "coordinator": {
        "view_all_patients",
        "manage_tasks",
        "coordinator_board",
        "view_analyses",
        "view_patients",
    },
    "provider": {
        "view_assigned_patients",
        "create_encounters",
        "run_analyses",
        "provider_dashboard",
        "view_patients",
    },
    "specialist": {
        "view_assigned_patients",
        "create_encounters",
        "run_analyses",
        "provider_dashboard",
        "view_patients",
    },
    "nurse": {
        "view_assigned_patients",
        "create_encounters",
        "run_analyses",
        "provider_dashboard",
        "view_patients",
    },
    "patient": {
        "view_own_data",
        "checkin",
        "ask_questions",
        "view_medications",
        "view_symptoms",
        "view_appointments",
    },
    "caregiver": {
        "view_own_data",
        "checkin",
        "ask_questions",
        "view_medications",
        "view_symptoms",
        "view_appointments",
    },
}

DEMO_USERS = {
    "demo-admin@careloop.test": {
        "name": "Demo Admin",
        "role": "admin",
        "password": "demo1234",
        "patient_id": None,
    },
    "demo-coordinator@careloop.test": {
        "name": "Demo Coordinator",
        "role": "coordinator",
        "password": "demo1234",
        "patient_id": None,
    },
    "demo-provider@careloop.test": {
        "name": "Dr. Demo Provider",
        "role": "provider",
        "password": "demo1234",
        "patient_id": None,
    },
    "demo-specialist@careloop.test": {
        "name": "Dr. Demo Specialist",
        "role": "specialist",
        "password": "demo1234",
        "patient_id": None,
    },
    "demo-nurse@careloop.test": {
        "name": "Demo Nurse",
        "role": "nurse",
        "password": "demo1234",
        "patient_id": None,
    },
    "demo-patient@careloop.test": {
        "name": "Demo Patient",
        "role": "patient",
        "password": "demo1234",
        "patient_id": None,
    },
    "demo-caregiver@careloop.test": {
        "name": "Demo Caregiver",
        "role": "caregiver",
        "password": "demo1234",
        "patient_id": None,
    },
}


def hash_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )


def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt

    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def sign_token(token: str) -> str:
    signature = hashlib.sha256(f"{token}:{SECRET_KEY}".encode("utf-8")).hexdigest()
    return f"{token}.{signature}"


def verify_signed_token(signed_token: str) -> Optional[str]:
    if "." not in signed_token:
        return None
    token, signature = signed_token.rsplit(".", 1)
    expected = hashlib.sha256(f"{token}:{SECRET_KEY}".encode("utf-8")).hexdigest()
    if secrets.compare_digest(signature, expected):
        return token
    return None


def get_user_by_email(email: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def create_session(user_id: str) -> str:
    token = generate_token()
    signed = sign_token(token)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=SESSION_DURATION_HOURS)
    ).isoformat()

    with get_db() as db:
        db.execute(
            "INSERT INTO sessions (id, user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                user_id,
                token,
                expires_at,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return signed


def delete_session(token: str) -> None:
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def cleanup_expired_sessions() -> None:
    with get_db() as db:
        db.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (datetime.now(timezone.utc).isoformat(),),
        )


def authenticate(email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def login(response: Response, user: dict) -> Response:
    signed_token = create_session(user["id"])
    response.set_cookie(
        key="session_token",
        value=signed_token,
        httponly=True,
        secure=not DEMO_MODE,
        samesite="lax",
        max_age=SESSION_DURATION_HOURS * 3600,
        path="/",
    )
    return response


def logout(request: Request, response: Response) -> Response:
    signed_token = request.cookies.get("session_token")
    if signed_token:
        token = verify_signed_token(signed_token)
        if token:
            delete_session(token)
    response.delete_cookie(key="session_token", path="/")
    return response


def get_current_user(request: Request) -> Optional[dict]:
    if DEMO_MODE:
        return _get_demo_user(request)

    signed_token = request.cookies.get("session_token")
    if not signed_token:
        return None

    token = verify_signed_token(signed_token)
    if not token:
        return None

    with get_db() as db:
        session = db.execute(
            "SELECT * FROM sessions WHERE token = ? AND expires_at > ?",
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()

        if not session:
            return None

        user = db.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1",
            (session["user_id"],),
        ).fetchone()

        if not user:
            return None

        return dict(user)

    return None


def _get_demo_user(request: Request) -> Optional[dict]:
    demo_role = request.query_params.get("demo_role", "provider")
    if demo_role not in VALID_ROLES:
        demo_role = "provider"

    for email, info in DEMO_USERS.items():
        if info["role"] == demo_role:
            user = get_user_by_email(email)
            if user:
                return user
            with get_db() as db:
                user_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO users (id, email, password_hash, name, role, patient_id, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                    (
                        user_id,
                        email,
                        hash_password(info["password"]),
                        info["name"],
                        info["role"],
                        info["patient_id"],
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            return get_user_by_email(email)

    return None


def get_current_user_or_error(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def has_permission(role: str, permission: str) -> bool:
    if role not in ROLE_PERMISSIONS:
        return False
    perms = ROLE_PERMISSIONS[role]
    return "all" in perms or permission in perms


def require_role(*roles: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)
            if not user:
                accept = request.headers.get("accept", "")
                if "text/html" in accept:
                    return RedirectResponse(
                        url="/login?error=auth_required", status_code=303
                    )
                raise HTTPException(status_code=401, detail="Authentication required")

            if user["role"] not in roles:
                accept = request.headers.get("accept", "")
                if "text/html" in accept:
                    return RedirectResponse(url="/?error=forbidden", status_code=303)
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            request.state.user = user
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)
            if not user:
                accept = request.headers.get("accept", "")
                if "text/html" in accept:
                    return RedirectResponse(
                        url="/login?error=auth_required", status_code=303
                    )
                raise HTTPException(status_code=401, detail="Authentication required")

            if not has_permission(user["role"], permission):
                accept = request.headers.get("accept", "")
                if "text/html" in accept:
                    return RedirectResponse(url="/?error=forbidden", status_code=303)
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            request.state.user = user
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def can_access_patient(user: dict, patient_id: str) -> bool:
    role = user["role"]

    if has_permission(role, "all"):
        return True

    if has_permission(role, "view_all_patients"):
        return True

    if role in ("patient", "caregiver"):
        return user.get("patient_id") == patient_id

    if role in ("provider", "specialist", "nurse"):
        with get_db() as db:
            row = db.execute(
                "SELECT 1 FROM care_team WHERE patient_id = ? AND provider_id = ?",
                (patient_id, user["id"]),
            ).fetchone()
            return row is not None

    return False
