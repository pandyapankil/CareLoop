"""CareLoop — FastAPI application entry point."""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.database import init_db, get_db
from app.routers import symptoms, messages, notifications

# Initialize app
app = FastAPI(
    title=os.getenv("APP_NAME", "CareLoop"),
    description="AI-powered care coordination using GLM 5.1",
    version="1.0.0",
)

# Static files and templates
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(symptoms.router)
app.include_router(messages.router)
app.include_router(notifications.router)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()


# ─── Health Check ────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check for deployment."""
    return JSONResponse(
        {"status": "healthy", "service": "CareLoop", "version": "1.0.0"}
    )


# ─── Home Page ───────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard showing all patients."""
    with get_db() as db:
        patients = db.execute(
            "SELECT * FROM patients ORDER BY created_at DESC"
        ).fetchall()

        # Get encounter counts per patient
        patient_list = []
        for p in patients:
            count = db.execute(
                "SELECT COUNT(*) as cnt FROM encounters WHERE patient_id = ?",
                (p["id"],),
            ).fetchone()["cnt"]

            analysis_count = db.execute(
                "SELECT COUNT(*) as cnt FROM glm_analyses WHERE patient_id = ?",
                (p["id"],),
            ).fetchone()["cnt"]

            patient_list.append(
                {
                    **dict(p),
                    "encounter_count": count,
                    "analysis_count": analysis_count,
                }
            )

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "patients": patient_list,
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


# ─── Patient Timeline ───────────────────────────────────────
@app.get("/patient/{patient_id}", response_class=HTMLResponse)
async def patient_timeline(request: Request, patient_id: str):
    """Patient detail page with timeline of encounters and analyses."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()

        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        encounters = db.execute(
            "SELECT * FROM encounters WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

        analyses = db.execute(
            "SELECT * FROM glm_analyses WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

        tasks = db.execute(
            "SELECT * FROM tasks WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

        qa_exchanges = db.execute(
            "SELECT * FROM qa_exchanges WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

        # Build unified timeline
        timeline = []
        for e in encounters:
            timeline.append(
                {"type": "encounter", "data": dict(e), "at": e["created_at"]}
            )
        for a in analyses:
            timeline.append(
                {"type": "analysis", "data": dict(a), "at": a["created_at"]}
            )
        for q in qa_exchanges:
            timeline.append({"type": "qa", "data": dict(q), "at": q["created_at"]})

        timeline.sort(key=lambda x: x["at"], reverse=True)

    return templates.TemplateResponse(
        "patient.html",
        {
            "request": request,
            "patient": dict(patient),
            "timeline": timeline,
            "tasks": [dict(t) for t in tasks],
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


# ─── Provider Update ─────────────────────────────────────────
@app.get("/patient/{patient_id}/provider-update", response_class=HTMLResponse)
async def provider_update_form(request: Request, patient_id: str):
    """Show provider update form."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    return templates.TemplateResponse(
        "provider_update.html",
        {
            "request": request,
            "patient": dict(patient),
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@app.post("/patient/{patient_id}/provider-update")
async def submit_provider_update(
    patient_id: str, author_name: str = Form(...), content: str = Form(...)
):
    """Submit a provider clinical update."""
    with get_db() as db:
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                patient_id,
                "provider",
                author_name,
                "provider_update",
                content,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return RedirectResponse(f"/patient/{patient_id}", status_code=303)


# ─── Patient Check-in ────────────────────────────────────────
@app.get("/patient/{patient_id}/checkin", response_class=HTMLResponse)
async def checkin_form(request: Request, patient_id: str):
    """Show patient check-in form."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    return templates.TemplateResponse(
        "checkin.html",
        {
            "request": request,
            "patient": dict(patient),
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@app.post("/patient/{patient_id}/checkin")
async def submit_checkin(patient_id: str, content: str = Form(...)):
    """Submit a patient check-in."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                patient_id,
                "patient",
                patient["name"],
                "patient_checkin",
                content,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return RedirectResponse(f"/patient/{patient_id}", status_code=303)


# ─── GLM Analysis ────────────────────────────────────────────
@app.post("/patient/{patient_id}/analyze")
async def run_analysis(patient_id: str):
    """Trigger GLM 5.1 care analysis for a patient."""
    from app.services.glm_service import run_care_analysis

    result = await run_care_analysis(patient_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/patient/{patient_id}", status_code=303)


@app.get("/analysis/{analysis_id}", response_class=HTMLResponse)
async def analysis_detail(request: Request, analysis_id: str):
    """View full analysis with AI transparency panel."""
    with get_db() as db:
        analysis = db.execute(
            "SELECT * FROM glm_analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        if not analysis:
            return HTMLResponse("<h1>Analysis not found</h1>", status_code=404)

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (analysis["patient_id"],)
        ).fetchone()

        tasks = db.execute(
            "SELECT * FROM tasks WHERE analysis_id = ?", (analysis_id,)
        ).fetchall()

        # Parse JSON fields
        risk_flags = json.loads(analysis["risk_flags_json"] or "[]")
        tasks_from_analysis = json.loads(analysis["tasks_json"] or "[]")

    return templates.TemplateResponse(
        "analysis.html",
        {
            "request": request,
            "analysis": dict(analysis),
            "patient": dict(patient),
            "risk_flags": risk_flags,
            "tasks_from_analysis": tasks_from_analysis,
            "tasks": [dict(t) for t in tasks],
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


# ─── Patient Q&A ─────────────────────────────────────────────
@app.get("/patient/{patient_id}/ask", response_class=HTMLResponse)
async def ask_form(request: Request, patient_id: str):
    """Show patient Q&A form."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        qa_history = db.execute(
            "SELECT * FROM qa_exchanges WHERE patient_id = ? ORDER BY created_at DESC LIMIT 10",
            (patient_id,),
        ).fetchall()

    return templates.TemplateResponse(
        "ask.html",
        {
            "request": request,
            "patient": dict(patient),
            "qa_history": [dict(q) for q in qa_history],
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


@app.post("/patient/{patient_id}/ask")
async def submit_question(patient_id: str, question: str = Form(...)):
    """Submit a patient question to GLM 5.1."""
    from app.services.glm_service import run_patient_qa

    result = await run_patient_qa(patient_id, question)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/patient/{patient_id}/ask", status_code=303)


# ─── Trend Detection ─────────────────────────────────────────
@app.post("/patient/{patient_id}/trends")
async def detect_trends(patient_id: str):
    """Run GLM 5.1 trend detection across patient analyses."""
    from app.services.glm_service import run_trend_detection

    result = await run_trend_detection(patient_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/patient/{patient_id}", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        reload=os.getenv("DEBUG", "true").lower() == "true",
    )
