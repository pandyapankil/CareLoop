import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter(tags=["analytics"])

BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request):
    with get_db() as db:
        total_tasks = db.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        completed_on_time = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status = 'completed' AND (due_date IS NULL OR completed_at <= due_date)"
        ).fetchone()["cnt"]
        overdue_tasks = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status != 'completed' AND due_date IS NOT NULL AND due_date < datetime('now')"
        ).fetchone()["cnt"]

        on_time_rate = round(
            (completed_on_time / total_tasks * 100) if total_tasks > 0 else 0, 1
        )
        overdue_rate = round(
            (overdue_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1
        )

        total_patients = db.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()[
            "cnt"
        ]
        total_encounters = db.execute(
            "SELECT COUNT(*) as cnt FROM encounters"
        ).fetchone()["cnt"]
        encounters_per_patient = round(
            (total_encounters / total_patients) if total_patients > 0 else 0, 1
        )

        patient_checkins = db.execute(
            "SELECT COUNT(*) as cnt FROM encounters WHERE type = 'patient_checkin'"
        ).fetchone()["cnt"]
        checkin_frequency = round(
            (patient_checkins / total_patients) if total_patients > 0 else 0, 1
        )

        analyses_run = db.execute(
            "SELECT COUNT(*) as cnt FROM glm_analyses"
        ).fetchone()["cnt"]
        qa_exchanges = db.execute(
            "SELECT COUNT(*) as cnt FROM qa_exchanges"
        ).fetchone()["cnt"]

        risk_high = 0
        risk_medium = 0
        risk_low = 0
        analyses = db.execute("SELECT risk_flags_json FROM glm_analyses").fetchall()
        for a in analyses:
            flags = json.loads(a["risk_flags_json"] or "[]")
            for f in flags:
                severity = f.get("severity", "medium")
                if severity == "high":
                    risk_high += 1
                elif severity == "medium":
                    risk_medium += 1
                else:
                    risk_low += 1

        task_by_owner = db.execute(
            "SELECT owner, COUNT(*) as cnt FROM tasks GROUP BY owner"
        ).fetchall()
        task_completion_by_owner = db.execute(
            "SELECT owner, COUNT(*) as total, SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed FROM tasks GROUP BY owner"
        ).fetchall()

        completion_rates = []
        for row in task_completion_by_owner:
            total = row["total"]
            completed = row["completed"]
            rate = round((completed / total * 100) if total > 0 else 0, 1)
            completion_rates.append(
                {
                    "owner": row["owner"],
                    "total": total,
                    "completed": completed,
                    "rate": rate,
                }
            )

        max_completion = max((r["rate"] for r in completion_rates), default=100)
        if max_completion == 0:
            max_completion = 100

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "on_time_rate": on_time_rate,
            "overdue_rate": overdue_rate,
            "total_tasks": total_tasks,
            "encounters_per_patient": encounters_per_patient,
            "checkin_frequency": checkin_frequency,
            "analyses_run": analyses_run,
            "qa_exchanges": qa_exchanges,
            "risk_high": risk_high,
            "risk_medium": risk_medium,
            "risk_low": risk_low,
            "completion_rates": completion_rates,
            "max_completion": max_completion,
        },
    )
