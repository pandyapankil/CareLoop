import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter(tags=["care-team"])

BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/patient/{patient_id}/care-team", response_class=HTMLResponse)
async def view_care_team(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        members = db.execute(
            "SELECT * FROM care_team WHERE patient_id = ? ORDER BY is_primary DESC, created_at ASC",
            (patient_id,),
        ).fetchall()

        providers = db.execute(
            "SELECT id, name, role FROM users WHERE role IN ('provider', 'coordinator') AND is_active = 1"
        ).fetchall()

    return templates.TemplateResponse(
        "care_team.html",
        {
            "request": request,
            "patient": dict(patient),
            "members": [dict(m) for m in members],
            "providers": [dict(p) for p in providers],
        },
    )


@router.get("/patient/{patient_id}/care-team/add", response_class=HTMLResponse)
async def add_member_form(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        providers = db.execute(
            "SELECT id, name, role FROM users WHERE role IN ('provider', 'coordinator') AND is_active = 1"
        ).fetchall()

    return templates.TemplateResponse(
        "care_team.html",
        {
            "request": request,
            "patient": dict(patient),
            "members": [],
            "providers": [dict(p) for p in providers],
            "show_add_form": True,
        },
    )


@router.post("/patient/{patient_id}/care-team/add")
async def add_member(
    patient_id: str,
    provider_id: str = Form(...),
    provider_name: str = Form(...),
    provider_role: str = Form(...),
):
    member_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM care_team WHERE patient_id = ? AND provider_id = ?",
            (patient_id, provider_id),
        ).fetchone()
        if existing:
            return RedirectResponse(f"/patient/{patient_id}/care-team", status_code=303)

        member_count = db.execute(
            "SELECT COUNT(*) as cnt FROM care_team WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()["cnt"]

        is_primary = 1 if member_count == 0 else 0

        db.execute(
            "INSERT INTO care_team (id, patient_id, provider_id, provider_name, provider_role, is_primary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                member_id,
                patient_id,
                provider_id,
                provider_name,
                provider_role,
                is_primary,
                now,
            ),
        )

    return RedirectResponse(f"/patient/{patient_id}/care-team", status_code=303)


@router.post("/care-team/{member_id}/remove")
async def remove_member(member_id: str):
    with get_db() as db:
        member = db.execute(
            "SELECT * FROM care_team WHERE id = ?", (member_id,)
        ).fetchone()
        if not member:
            return HTMLResponse("<h1>Team member not found</h1>", status_code=404)

        patient_id = member["patient_id"]
        db.execute("DELETE FROM care_team WHERE id = ?", (member_id,))

    return RedirectResponse(f"/patient/{patient_id}/care-team", status_code=303)


@router.post("/care-team/{member_id}/set-primary")
async def set_primary(member_id: str):
    with get_db() as db:
        member = db.execute(
            "SELECT * FROM care_team WHERE id = ?", (member_id,)
        ).fetchone()
        if not member:
            return HTMLResponse("<h1>Team member not found</h1>", status_code=404)

        patient_id = member["patient_id"]
        db.execute(
            "UPDATE care_team SET is_primary = 0 WHERE patient_id = ?", (patient_id,)
        )
        db.execute("UPDATE care_team SET is_primary = 1 WHERE id = ?", (member_id,))

    return RedirectResponse(f"/patient/{patient_id}/care-team", status_code=303)
