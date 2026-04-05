import uuid
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter(tags=["symptoms"])
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "templates"
)


@router.get("/patient/{patient_id}/symptoms", response_class=HTMLResponse)
async def symptom_list(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        entries = db.execute(
            "SELECT * FROM symptom_entries WHERE patient_id = ? ORDER BY logged_at DESC",
            (patient_id,),
        ).fetchall()

        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        rows = db.execute(
            "SELECT date(logged_at) as day, AVG(pain_level) as avg_pain, AVG(mood_level) as avg_mood, AVG(sleep_quality) as avg_sleep FROM symptom_entries WHERE patient_id = ? AND logged_at >= ? GROUP BY date(logged_at) ORDER BY day",
            (patient_id, thirty_days_ago),
        ).fetchall()

        trend_data = json.dumps(
            [
                {
                    "day": r["day"],
                    "pain": round(r["avg_pain"], 1),
                    "mood": round(r["avg_mood"], 1),
                    "sleep": round(r["avg_sleep"], 1),
                }
                for r in rows
            ]
        )

    return templates.TemplateResponse(
        "symptoms.html",
        {
            "request": request,
            "patient": dict(patient),
            "entries": [
                {**dict(e), "vitals": json.loads(dict(e).get("vitals_json") or "{}")}
                for e in entries
            ],
            "trend_data": trend_data,
        },
    )


@router.get("/patient/{patient_id}/symptoms/new", response_class=HTMLResponse)
async def symptom_form(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    return templates.TemplateResponse(
        "symptom_form.html",
        {
            "request": request,
            "patient": dict(patient),
        },
    )


@router.post("/patient/{patient_id}/symptoms/new")
async def create_symptom_entry(
    patient_id: str,
    pain_level: int = Form(0),
    mood_level: int = Form(5),
    sleep_quality: int = Form(5),
    blood_pressure_systolic: str = Form(""),
    blood_pressure_diastolic: str = Form(""),
    heart_rate: str = Form(""),
    temperature: str = Form(""),
    weight: str = Form(""),
    notes: str = Form(""),
):
    vitals = {}
    if blood_pressure_systolic and blood_pressure_diastolic:
        vitals["blood_pressure"] = (
            f"{blood_pressure_systolic}/{blood_pressure_diastolic}"
        )
    if heart_rate:
        vitals["heart_rate"] = heart_rate
    if temperature:
        vitals["temperature"] = temperature
    if weight:
        vitals["weight"] = weight

    with get_db() as db:
        db.execute(
            "INSERT INTO symptom_entries (id, patient_id, pain_level, mood_level, sleep_quality, vitals_json, notes, logged_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                patient_id,
                pain_level,
                mood_level,
                sleep_quality,
                json.dumps(vitals),
                notes,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return RedirectResponse(f"/patient/{patient_id}/symptoms", status_code=303)


@router.get("/symptom/{entry_id}", response_class=HTMLResponse)
async def symptom_detail(request: Request, entry_id: str):
    with get_db() as db:
        entry = db.execute(
            "SELECT * FROM symptom_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not entry:
            return HTMLResponse("<h1>Symptom entry not found</h1>", status_code=404)

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (entry["patient_id"],)
        ).fetchone()

    entry_dict = dict(entry)
    entry_dict["vitals"] = json.loads(entry_dict.get("vitals_json") or "{}")

    return templates.TemplateResponse(
        "symptom_form.html",
        {
            "request": request,
            "patient": dict(patient),
            "entry": entry_dict,
            "view_only": True,
        },
    )
