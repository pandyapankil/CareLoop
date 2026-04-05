import uuid
import json
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path

from app.database import get_db

BASE_DIR = Path(__file__).resolve().parent.parent
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(tags=["medications"])


def _calculate_adherence(db, medication_id: str) -> dict:
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    logs = db.execute(
        "SELECT status FROM medication_logs WHERE medication_id = ? AND taken_at >= ?",
        (medication_id, seven_days_ago),
    ).fetchall()

    total = len(logs)
    taken = sum(1 for log in logs if log["status"] == "taken")
    percentage = round((taken / total) * 100) if total > 0 else 0

    return {
        "total_logs": total,
        "taken": taken,
        "skipped": sum(1 for log in logs if log["status"] == "skipped"),
        "missed": sum(1 for log in logs if log["status"] == "missed"),
        "percentage": percentage,
    }


@router.get("/patient/{patient_id}/medications", response_class=HTMLResponse)
async def list_medications(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        medications = db.execute(
            "SELECT * FROM medications WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

        med_list = []
        for med in medications:
            med_dict = dict(med)
            med_dict["adherence"] = _calculate_adherence(db, med["id"])
            med_list.append(med_dict)

    return templates.TemplateResponse(
        "medications.html",
        {
            "request": request,
            "patient": dict(patient),
            "medications": med_list,
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@router.get("/patient/{patient_id}/medications/new", response_class=HTMLResponse)
async def new_medication_form(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        providers = db.execute(
            "SELECT DISTINCT u.id, u.name FROM users u "
            "LEFT JOIN care_team ct ON ct.provider_id = u.id AND ct.patient_id = ? "
            "WHERE u.role = 'provider' OR ct.patient_id = ?",
            (patient_id, patient_id),
        ).fetchall()

    return templates.TemplateResponse(
        "medication_form.html",
        {
            "request": request,
            "patient": dict(patient),
            "providers": [dict(p) for p in providers],
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@router.post("/patient/{patient_id}/medications/new")
async def create_medication(
    patient_id: str,
    name: str = Form(...),
    dosage: str = Form(...),
    frequency: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(""),
    prescribed_by: str = Form(""),
    instructions: str = Form(""),
    side_effects: str = Form(""),
):
    medication_id = str(uuid.uuid4())

    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        db.execute(
            "INSERT INTO medications "
            "(id, patient_id, name, dosage, frequency, start_date, end_date, "
            "prescribed_by, instructions, side_effects, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                medication_id,
                patient_id,
                name,
                dosage,
                frequency,
                start_date,
                end_date or None,
                prescribed_by,
                instructions,
                side_effects,
                "active",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return RedirectResponse(f"/patient/{patient_id}/medications", status_code=303)


@router.get("/medication/{medication_id}", response_class=HTMLResponse)
async def medication_detail(request: Request, medication_id: str):
    with get_db() as db:
        medication = db.execute(
            "SELECT * FROM medications WHERE id = ?", (medication_id,)
        ).fetchone()
        if not medication:
            return HTMLResponse("<h1>Medication not found</h1>", status_code=404)

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (medication["patient_id"],)
        ).fetchone()

        logs = db.execute(
            "SELECT * FROM medication_logs WHERE medication_id = ? "
            "ORDER BY taken_at DESC LIMIT 30",
            (medication_id,),
        ).fetchall()

        adherence = _calculate_adherence(db, medication_id)

    return templates.TemplateResponse(
        "medication_detail.html",
        {
            "request": request,
            "patient": dict(patient),
            "medication": dict(medication),
            "logs": [dict(log) for log in logs],
            "adherence": adherence,
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@router.post("/medication/{medication_id}/log")
async def log_medication(
    medication_id: str,
    status: str = Form("taken"),
    notes: str = Form(""),
):
    valid_statuses = {"taken", "skipped", "missed"}
    if status not in valid_statuses:
        return HTMLResponse("<h1>Invalid log status</h1>", status_code=400)

    with get_db() as db:
        medication = db.execute(
            "SELECT * FROM medications WHERE id = ?", (medication_id,)
        ).fetchone()
        if not medication:
            return HTMLResponse("<h1>Medication not found</h1>", status_code=404)

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        db.execute(
            "INSERT INTO medication_logs "
            "(id, medication_id, patient_id, taken_at, status, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                log_id,
                medication_id,
                medication["patient_id"],
                now,
                status,
                notes,
                now,
            ),
        )

    return RedirectResponse(f"/medication/{medication_id}", status_code=303)


@router.post("/medication/{medication_id}/refill")
async def request_refill(medication_id: str):
    with get_db() as db:
        medication = db.execute(
            "SELECT * FROM medications WHERE id = ?", (medication_id,)
        ).fetchone()
        if not medication:
            return HTMLResponse("<h1>Medication not found</h1>", status_code=404)

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (medication["patient_id"],)
        ).fetchone()

        providers = db.execute(
            "SELECT provider_id FROM care_team WHERE patient_id = ?",
            (medication["patient_id"],),
        ).fetchall()

        notification_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        if providers:
            for provider in providers:
                db.execute(
                    "INSERT INTO notifications "
                    "(id, user_id, type, title, body, related_id, related_type, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        provider["provider_id"],
                        "refill_request",
                        f"Refill Request: {medication['name']}",
                        f"Patient {patient['name']} has requested a refill for {medication['name']} ({medication['dosage']}).",
                        medication_id,
                        "medication",
                        now,
                    ),
                )
        else:
            users = db.execute(
                "SELECT id FROM users WHERE role = 'provider' LIMIT 1"
            ).fetchall()
            for user in users:
                db.execute(
                    "INSERT INTO notifications "
                    "(id, user_id, type, title, body, related_id, related_type, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        user["id"],
                        "refill_request",
                        f"Refill Request: {medication['name']}",
                        f"Patient {patient['name']} has requested a refill for {medication['name']} ({medication['dosage']}).",
                        medication_id,
                        "medication",
                        now,
                    ),
                )

    return RedirectResponse(f"/medication/{medication_id}", status_code=303)
