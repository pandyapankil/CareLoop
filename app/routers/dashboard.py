import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter(tags=["dashboard"])

BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/dashboard/provider", response_class=HTMLResponse)
async def provider_dashboard(request: Request):
    now = datetime.now(timezone.utc)
    week_ahead = (now + timedelta(days=7)).isoformat()

    with get_db() as db:
        overdue_tasks = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status != 'completed' AND due_date IS NOT NULL AND due_date < ?",
            (now.isoformat(),),
        ).fetchone()["cnt"]

        pending_reviews = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE status = 'pending'",
        ).fetchone()["cnt"]

        unanswered_messages = db.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE read = 0",
        ).fetchone()["cnt"]

        upcoming_appointments = db.execute(
            "SELECT a.*, p.name as patient_name FROM appointments a JOIN patients p ON a.patient_id = p.id WHERE a.scheduled_at > ? AND a.scheduled_at < ? AND a.status = 'scheduled' ORDER BY a.scheduled_at ASC",
            (now.isoformat(), week_ahead),
        ).fetchall()

        patients = db.execute(
            "SELECT * FROM patients ORDER BY created_at DESC"
        ).fetchall()
        patient_snapshots = []
        for p in patients:
            latest_encounter = db.execute(
                "SELECT created_at FROM encounters WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1",
                (p["id"],),
            ).fetchone()
            pending = db.execute(
                "SELECT COUNT(*) as cnt FROM tasks WHERE patient_id = ? AND status != 'completed'",
                (p["id"],),
            ).fetchone()["cnt"]
            patient_snapshots.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "condition": p["condition"],
                    "latest_activity": latest_encounter["created_at"]
                    if latest_encounter
                    else None,
                    "pending_tasks": pending,
                }
            )

    return templates.TemplateResponse(
        "provider_dashboard.html",
        {
            "request": request,
            "overdue_tasks": overdue_tasks,
            "pending_reviews": pending_reviews,
            "unanswered_messages": unanswered_messages,
            "upcoming_appointments": [dict(a) for a in upcoming_appointments],
            "patient_snapshots": patient_snapshots,
        },
    )


@router.get("/dashboard/coordinator", response_class=HTMLResponse)
async def coordinator_dashboard(request: Request):
    now = datetime.now(timezone.utc)
    overdue_threshold = (now - timedelta(hours=48)).isoformat()

    with get_db() as db:
        overdue_tasks = db.execute(
            "SELECT t.*, p.name as patient_name FROM tasks t JOIN patients p ON t.patient_id = p.id WHERE t.status != 'completed' AND t.due_date IS NOT NULL AND t.due_date < ? ORDER BY t.due_date ASC",
            (overdue_threshold,),
        ).fetchall()

        outreach_queue = db.execute(
            "SELECT t.*, p.name as patient_name FROM tasks t JOIN patients p ON t.patient_id = p.id WHERE t.status = 'pending' AND t.owner = 'patient' ORDER BY t.created_at ASC",
        ).fetchall()

        missing_documents = db.execute(
            "SELECT p.name as patient_name, p.id as patient_id FROM patients p LEFT JOIN documents d ON p.id = d.patient_id WHERE d.id IS NULL",
        ).fetchall()

        escalation_queue = db.execute(
            "SELECT t.*, p.name as patient_name FROM tasks t JOIN patients p ON t.patient_id = p.id WHERE t.status != 'completed' AND t.due_date IS NOT NULL AND t.due_date < ? ORDER BY t.due_date ASC",
            (now.isoformat(),),
        ).fetchall()

        total_patients = db.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()[
            "cnt"
        ]
        overdue_count = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status != 'completed' AND due_date IS NOT NULL AND due_date < ?",
            (now.isoformat(),),
        ).fetchone()["cnt"]
        pending_review_count = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE status = 'pending'",
        ).fetchone()["cnt"]

    return templates.TemplateResponse(
        "coordinator_dashboard.html",
        {
            "request": request,
            "overdue_tasks": [dict(t) for t in overdue_tasks],
            "outreach_queue": [dict(t) for t in outreach_queue],
            "missing_documents": [dict(d) for d in missing_documents],
            "escalation_queue": [dict(t) for t in escalation_queue],
            "total_patients": total_patients,
            "overdue_count": overdue_count,
            "pending_review_count": pending_review_count,
        },
    )


@router.get("/dashboard/patient", response_class=HTMLResponse)
async def patient_dashboard(request: Request):
    now = datetime.now(timezone.utc)

    with get_db() as db:
        patient = db.execute("SELECT * FROM patients LIMIT 1").fetchone()
        if not patient:
            return HTMLResponse("<h1>No patient found</h1>", status_code=404)

        patient_id = patient["id"]

        next_appointment = db.execute(
            "SELECT * FROM appointments WHERE patient_id = ? AND scheduled_at > ? AND status = 'scheduled' ORDER BY scheduled_at ASC LIMIT 1",
            (patient_id, now.isoformat()),
        ).fetchone()

        countdown = None
        if next_appointment:
            appt_dt = datetime.fromisoformat(next_appointment["scheduled_at"])
            delta = appt_dt - now
            countdown = {
                "days": delta.days,
                "hours": delta.seconds // 3600,
                "label": next_appointment["title"],
                "date": next_appointment["scheduled_at"],
            }

        pending_tasks = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE patient_id = ? AND status = 'pending'",
            (patient_id,),
        ).fetchone()["cnt"]

        overdue_tasks = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE patient_id = ? AND status != 'completed' AND due_date IS NOT NULL AND due_date < ?",
            (patient_id, now.isoformat()),
        ).fetchone()["cnt"]

        medications = db.execute(
            "SELECT * FROM medications WHERE patient_id = ? AND status = 'active' ORDER BY name ASC",
            (patient_id,),
        ).fetchall()

        symptoms = db.execute(
            "SELECT * FROM symptom_entries WHERE patient_id = ? ORDER BY logged_at DESC LIMIT 7",
            (patient_id,),
        ).fetchall()

        symptom_trend = []
        for s in reversed(symptoms):
            symptom_trend.append(
                {
                    "date": s["logged_at"][:10],
                    "pain": s["pain_level"],
                    "mood": s["mood_level"],
                    "sleep": s["sleep_quality"],
                }
            )

    return templates.TemplateResponse(
        "patient_dashboard.html",
        {
            "request": request,
            "patient": dict(patient),
            "next_appointment": dict(next_appointment) if next_appointment else None,
            "countdown": countdown,
            "pending_tasks": pending_tasks,
            "overdue_tasks": overdue_tasks,
            "medications": [dict(m) for m in medications],
            "symptom_trend": symptom_trend,
        },
    )


@router.get("/dashboard/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    with get_db() as db:
        user_count = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        patient_count = db.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()[
            "cnt"
        ]
        encounter_count = db.execute(
            "SELECT COUNT(*) as cnt FROM encounters"
        ).fetchone()["cnt"]
        analysis_count = db.execute(
            "SELECT COUNT(*) as cnt FROM glm_analyses"
        ).fetchone()["cnt"]

        recent_activity = db.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 20",
        ).fetchall()

        users = db.execute(
            "SELECT id, name, email, role, is_active FROM users ORDER BY created_at DESC"
        ).fetchall()

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "user_count": user_count,
            "patient_count": patient_count,
            "encounter_count": encounter_count,
            "analysis_count": analysis_count,
            "recent_activity": [dict(a) for a in recent_activity],
            "users": [dict(u) for u in users],
        },
    )
