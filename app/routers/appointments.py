import uuid
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path

from app.database import get_db
from app.utils.countdown import format_countdown

BASE_DIR = Path(__file__).resolve().parent.parent
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(tags=["appointments"])


@router.get("/patient/{patient_id}/appointments", response_class=HTMLResponse)
async def list_appointments(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        appointments = db.execute(
            "SELECT a.*, u.name as provider_name FROM appointments a "
            "LEFT JOIN users u ON a.provider_id = u.id "
            "WHERE a.patient_id = ? ORDER BY a.scheduled_at DESC",
            (patient_id,),
        ).fetchall()

        appointment_list = []
        for apt in appointments:
            apt_dict = dict(apt)
            apt_dict["countdown"] = format_countdown(apt["scheduled_at"])
            checklist = json.loads(apt["prep_checklist_json"] or "[]")
            completed = sum(1 for item in checklist if item.get("completed"))
            apt_dict["checklist_total"] = len(checklist)
            apt_dict["checklist_completed"] = completed
            appointment_list.append(apt_dict)

    return templates.TemplateResponse(
        "appointments.html",
        {
            "request": request,
            "patient": dict(patient),
            "appointments": appointment_list,
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@router.get("/patient/{patient_id}/appointments/new", response_class=HTMLResponse)
async def new_appointment_form(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        providers = db.execute(
            "SELECT u.id, u.name, ct.provider_role FROM users u "
            "LEFT JOIN care_team ct ON ct.provider_id = u.id AND ct.patient_id = ? "
            "WHERE u.role = 'provider' OR ct.patient_id = ?",
            (patient_id, patient_id),
        ).fetchall()

    return templates.TemplateResponse(
        "appointment_form.html",
        {
            "request": request,
            "patient": dict(patient),
            "providers": [dict(p) for p in providers],
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@router.post("/patient/{patient_id}/appointments/new")
async def create_appointment(
    patient_id: str,
    title: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
    location_url: str = Form(""),
    scheduled_at: str = Form(...),
    duration_minutes: int = Form(30),
    provider_id: str = Form(""),
    prep_checklist: str = Form("[]"),
):
    checklist_items = json.loads(prep_checklist) if prep_checklist else []
    checklist_json = json.dumps(
        [
            {"item": item.get("item", ""), "completed": False}
            for item in checklist_items
            if item.get("item", "").strip()
        ]
    )

    appointment_id = str(uuid.uuid4())

    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        if not provider_id:
            provider_id = str(uuid.uuid4())

        db.execute(
            "INSERT INTO appointments "
            "(id, patient_id, provider_id, title, description, location, location_url, "
            "scheduled_at, duration_minutes, status, prep_checklist_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                appointment_id,
                patient_id,
                provider_id,
                title,
                description,
                location,
                location_url,
                scheduled_at,
                duration_minutes,
                "scheduled",
                checklist_json,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return RedirectResponse(f"/patient/{patient_id}/appointments", status_code=303)


@router.get("/appointment/{appointment_id}", response_class=HTMLResponse)
async def appointment_detail(request: Request, appointment_id: str):
    with get_db() as db:
        appointment = db.execute(
            "SELECT a.*, u.name as provider_name FROM appointments a "
            "LEFT JOIN users u ON a.provider_id = u.id "
            "WHERE a.id = ?",
            (appointment_id,),
        ).fetchone()
        if not appointment:
            return HTMLResponse("<h1>Appointment not found</h1>", status_code=404)

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (appointment["patient_id"],)
        ).fetchone()

        apt_dict = dict(appointment)
        apt_dict["countdown"] = format_countdown(appointment["scheduled_at"])
        apt_dict["prep_checklist"] = json.loads(
            appointment["prep_checklist_json"] or "[]"
        )
        completed = sum(
            1 for item in apt_dict["prep_checklist"] if item.get("completed")
        )
        apt_dict["checklist_total"] = len(apt_dict["prep_checklist"])
        apt_dict["checklist_completed"] = completed

    return templates.TemplateResponse(
        "appointment_detail.html",
        {
            "request": request,
            "patient": dict(patient),
            "appointment": apt_dict,
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@router.post("/appointment/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    status: str = Form(...),
):
    valid_statuses = {"scheduled", "confirmed", "completed", "canceled"}
    if status not in valid_statuses:
        return HTMLResponse("<h1>Invalid status</h1>", status_code=400)

    with get_db() as db:
        appointment = db.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
        if not appointment:
            return HTMLResponse("<h1>Appointment not found</h1>", status_code=404)

        db.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (status, appointment_id),
        )

    return RedirectResponse(f"/appointment/{appointment_id}", status_code=303)


@router.post("/appointment/{appointment_id}/checklist")
async def toggle_checklist_item(
    appointment_id: str,
    item_index: int = Form(...),
):
    with get_db() as db:
        appointment = db.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
        if not appointment:
            return HTMLResponse("<h1>Appointment not found</h1>", status_code=404)

        checklist = json.loads(appointment["prep_checklist_json"] or "[]")
        if 0 <= item_index < len(checklist):
            checklist[item_index]["completed"] = not checklist[item_index].get(
                "completed", False
            )
            db.execute(
                "UPDATE appointments SET prep_checklist_json = ? WHERE id = ?",
                (json.dumps(checklist), appointment_id),
            )

    return RedirectResponse(f"/appointment/{appointment_id}", status_code=303)
