import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import get_db
from app.middleware.auth import (
    DEMO_MODE,
    authenticate,
    create_session,
    delete_session,
    get_user_by_email,
    hash_password,
    login,
    logout as auth_logout,
    verify_signed_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "templates"
)

ROLE_DASHBOARDS = {
    "patient": "/",
    "provider": "/",
    "specialist": "/",
    "nurse": "/",
    "coordinator": "/",
    "admin": "/",
}

DEMO_PERSONAS = [
    {
        "role": "patient",
        "name": "Maria Santos",
        "icon": "🏥",
        "desc": "Post-cardiac surgery recovery. View your care timeline and check in.",
    },
    {
        "role": "provider",
        "name": "Dr. James Chen",
        "icon": "👨‍⚕️",
        "desc": "Cardiologist. Manage patients, write updates, and review AI analyses.",
    },
    {
        "role": "specialist",
        "name": "Dr. Sarah Patel",
        "icon": "🔬",
        "desc": "Endocrinologist. Coordinate care for complex chronic conditions.",
    },
    {
        "role": "nurse",
        "name": "Nurse Kim",
        "icon": "🩺",
        "desc": "Care coordination nurse. Track patient progress and manage tasks.",
    },
    {
        "role": "coordinator",
        "name": "Coord. Alex",
        "icon": "📋",
        "desc": "Orchestrate care plans, schedule appointments, and connect the team.",
    },
    {
        "role": "admin",
        "name": "Admin User",
        "icon": "⚙️",
        "desc": "Full system access. Manage users, settings, and audit logs.",
    },
]

DEMO_EMAIL_MAP = {
    "patient": "patient@demo.com",
    "provider": "provider@demo.com",
    "specialist": "specialist@demo.com",
    "nurse": "nurse@demo.com",
    "coordinator": "coordinator@demo.com",
    "admin": "admin@demo.com",
}


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "demo_mode": DEMO_MODE,
            "error": None,
            "personas": DEMO_PERSONAS,
        },
    )


@router.post("/login")
async def login_submit(
    request: Request, email: str = Form(...), password: str = Form(...)
):
    user = authenticate(email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "demo_mode": DEMO_MODE,
                "error": "Invalid email or password.",
                "personas": DEMO_PERSONAS,
            },
            status_code=401,
        )

    response = RedirectResponse(
        url=ROLE_DASHBOARDS.get(user["role"], "/"),
        status_code=303,
    )
    return login(response, user)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "error": None,
        },
    )


@router.post("/register")
async def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    date_of_birth: str = Form(None),
    condition: str = Form(None),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Passwords do not match.",
            },
            status_code=400,
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Password must be at least 8 characters.",
            },
            status_code=400,
        )

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "error": "An account with this email already exists.",
                },
                status_code=409,
            )

        patient_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes) VALUES (?, ?, ?, ?, ?)",
            (patient_id, name, date_of_birth or "", condition or "General", ""),
        )

        user_id = str(uuid.uuid4())
        pw_hash = hash_password(password)
        db.execute(
            "INSERT INTO users (id, email, password_hash, name, role, patient_id) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email, pw_hash, name, "patient", patient_id),
        )

    user = get_user_by_email(email)
    response = RedirectResponse(url="/", status_code=303)
    return login(response, user)


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=303)
    return auth_logout(request, response)


@router.get("/demo-switch/{role}")
async def demo_switch(request: Request, role: str):
    if not DEMO_MODE:
        return RedirectResponse(url="/auth/login", status_code=303)

    email = DEMO_EMAIL_MAP.get(role)
    if not email:
        return RedirectResponse(url="/auth/login", status_code=303)

    user = get_user_by_email(email)
    if not user:
        with get_db() as db:
            user_id = str(uuid.uuid4())
            persona = next((p for p in DEMO_PERSONAS if p["role"] == role), None)
            patient_id = None
            if role == "patient":
                patient_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO patients (id, name, date_of_birth, condition, notes) VALUES (?, ?, ?, ?, ?)",
                    (
                        patient_id,
                        persona["name"] if persona else "Demo Patient",
                        "",
                        "General",
                        "",
                    ),
                )
            db.execute(
                "INSERT INTO users (id, email, password_hash, name, role, patient_id, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
                (
                    user_id,
                    email,
                    hash_password("demo"),
                    persona["name"] if persona else role.title(),
                    role,
                    patient_id,
                ),
            )
        user = get_user_by_email(email)

    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    response = RedirectResponse(
        url=ROLE_DASHBOARDS.get(user["role"], "/"),
        status_code=303,
    )
    return login(response, user)
