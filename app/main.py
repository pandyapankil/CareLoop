"""CareLoop — FastAPI application entry point."""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)

from app.database import init_db, get_db
from app.routers import (
    symptoms,
    messages,
    notifications,
    auth,
    appointments,
    medications,
    documents,
    careteam,
    dashboard,
    analytics,
    settings,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=os.getenv("APP_NAME", "CareLoop"),
    description="AI-powered care coordination using GLM 5.1",
    version="1.0.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

for r in [
    symptoms,
    messages,
    notifications,
    auth,
    appointments,
    medications,
    documents,
    careteam,
    dashboard,
    analytics,
    settings,
]:
    app.include_router(r.router)


# ─── Health Check ────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return JSONResponse(
        {"status": "healthy", "service": "CareLoop", "version": "1.0.0"}
    )


# ─── Usage Dashboard ───────────────────────────────────────────
@app.get("/api/usage")
async def get_usage_stats():
    from app.services.glm_service import get_usage

    return JSONResponse(get_usage())


@app.get("/usage", response_class=HTMLResponse)
async def usage_page(request: Request):
    return templates.TemplateResponse(
        "usage.html",
        {"request": request, "glm_available": bool(os.getenv("GLM_API_KEY"))},
    )


# ─── GLM 5.1 Streaming Analysis ────────────────────────────────
@app.get("/api/stream/analyze/{patient_id}")
async def stream_analysis(patient_id: str):
    from app.services.glm_service import (
        stream_glm,
        ANALYSIS_SYSTEM_PROMPT,
        ANALYSIS_TEMPLATE,
        get_db,
    )

    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return JSONResponse({"error": "Patient not found"}, status_code=404)

        encounters = db.execute(
            "SELECT * FROM encounters WHERE patient_id = ? ORDER BY created_at ASC",
            (patient_id,),
        ).fetchall()

        encounter_text = "\n".join(
            f"[{e['created_at']}] {e['author_role'].upper()}: {e['content']}"
            for e in encounters
        )

        user_content = ANALYSIS_TEMPLATE.format(
            name=patient["name"],
            condition=patient["condition"],
            notes=patient["notes"] or "N/A",
            encounters=encounter_text,
        )

    async def generate():
        from app.services.glm_service import StreamEventType

        async for chunk in stream_glm(
            [{"role": "user", "content": user_content}],
            ANALYSIS_SYSTEM_PROMPT,
            tools=True,
            patient_id=patient_id,
        ):
            chunk_data = {"event": chunk.event, "content": chunk.content}
            if chunk.tool_name:
                chunk_data["tool_name"] = chunk.tool_name
                chunk_data["tool_args"] = chunk.tool_args
            yield f"data: {json.dumps(chunk_data)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── GLM 5.1 Streaming Care Plan ──────────────────────────
@app.get("/api/stream/careplan/{patient_id}")
async def stream_careplan(patient_id: str):
    from app.services.glm_service import stream_careplan_generation, StreamEventType

    async def generate():
        async for chunk in stream_careplan_generation(patient_id):
            chunk_data = {"event": chunk.event, "content": chunk.content}
            if chunk.tool_name:
                chunk_data["tool_name"] = chunk.tool_name
                chunk_data["tool_args"] = chunk.tool_args
            yield f"data: {json.dumps(chunk_data)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── GLM 5.1 Streaming Trends ────────────────────────────
@app.get("/api/stream/trends/{patient_id}")
async def stream_trends(patient_id: str):
    from app.services.glm_service import stream_trend_detection, StreamEventType

    async def generate():
        async for chunk in stream_trend_detection(patient_id):
            chunk_data = {"event": chunk.event, "content": chunk.content}
            yield f"data: {json.dumps(chunk_data)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── GLM 5.1 Streaming Q&A ───────────────────────────────
@app.get("/api/stream/qa/{patient_id}")
async def stream_qa(patient_id: str, question: str = ""):
    from app.services.glm_service import stream_patient_qa, StreamEventType

    if not question:
        return JSONResponse({"error": "Question required"}, status_code=400)

    async def generate():
        async for chunk in stream_patient_qa(patient_id, question):
            chunk_data = {"event": chunk.event, "content": chunk.content}
            yield f"data: {json.dumps(chunk_data)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── GLM 5.1 Streaming Encounter Summary ──────────────────
@app.get("/api/stream/encounter/{encounter_id}/summarize")
async def stream_encounter_summary(encounter_id: str):
    from app.services.glm_service import stream_encounter_summary as _stream

    async def generate():
        async for chunk in _stream(encounter_id):
            chunk_data = {"event": chunk.event, "content": chunk.content}
            yield f"data: {json.dumps(chunk_data)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── GLM 5.1 Streaming Follow-up Suggestions ─────────────
@app.get("/api/stream/analysis/{analysis_id}/followups")
async def stream_followups(analysis_id: str):
    from app.services.glm_service import stream_followup_suggestions

    async def generate():
        async for chunk in stream_followup_suggestions(analysis_id):
            chunk_data = {"event": chunk.event, "content": chunk.content}
            yield f"data: {json.dumps(chunk_data)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Home Page ───────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with get_db() as db:
        patients = db.execute(
            "SELECT * FROM patients ORDER BY created_at DESC"
        ).fetchall()
        patient_list = []
        for p in patients:
            enc = db.execute(
                "SELECT COUNT(*) as cnt FROM encounters WHERE patient_id = ?",
                (p["id"],),
            ).fetchone()["cnt"]
            ana = db.execute(
                "SELECT COUNT(*) as cnt FROM glm_analyses WHERE patient_id = ?",
                (p["id"],),
            ).fetchone()["cnt"]
            patient_list.append(
                {**dict(p), "encounter_count": enc, "analysis_count": ana}
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
        care_plans = db.execute(
            "SELECT * FROM care_plans WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

        timeline = []
        for e in encounters:
            ed = dict(e)
            ed["structured_summary"] = None
            if e["structured_summary"]:
                try:
                    ed["structured_summary"] = json.loads(e["structured_summary"])
                except (json.JSONDecodeError, TypeError):
                    pass
            timeline.append({"type": "encounter", "data": ed, "at": e["created_at"]})

        for a in analyses:
            ad = dict(a)
            ad["followup_suggestions"] = None
            if a["followup_suggestions"]:
                try:
                    ad["followup_suggestions"] = json.loads(a["followup_suggestions"])
                except (json.JSONDecodeError, TypeError):
                    pass
            timeline.append({"type": "analysis", "data": ad, "at": a["created_at"]})

        for q in qa_exchanges:
            timeline.append({"type": "qa", "data": dict(q), "at": q["created_at"]})

        for cp in care_plans:
            cpd = dict(cp)
            cpd["plan_data"] = json.loads(cp["plan_json"])
            timeline.append({"type": "careplan", "data": cpd, "at": cp["created_at"]})

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


# ─── GLM 5.1 Care Analysis ──────────────────────────────────
@app.post("/patient/{patient_id}/analyze")
async def run_analysis(patient_id: str):
    from app.services.glm_service import run_care_analysis

    result = await run_care_analysis(patient_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/patient/{patient_id}", status_code=303)


@app.get("/analysis/{analysis_id}", response_class=HTMLResponse)
async def analysis_detail(request: Request, analysis_id: str):
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
        risk_flags = json.loads(analysis["risk_flags_json"] or "[]")
        tasks_from_analysis = json.loads(analysis["tasks_json"] or "[]")
        followup_suggestions = None
        if analysis["followup_suggestions"]:
            try:
                followup_suggestions = json.loads(analysis["followup_suggestions"])
            except (json.JSONDecodeError, TypeError):
                pass

    return templates.TemplateResponse(
        "analysis.html",
        {
            "request": request,
            "analysis": dict(analysis),
            "patient": dict(patient),
            "risk_flags": risk_flags,
            "tasks_from_analysis": tasks_from_analysis,
            "tasks": [dict(t) for t in tasks],
            "followup_suggestions": followup_suggestions,
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


# ─── Patient Q&A ─────────────────────────────────────────────
@app.get("/patient/{patient_id}/ask", response_class=HTMLResponse)
async def ask_form(request: Request, patient_id: str):
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
    from app.services.glm_service import run_patient_qa

    result = await run_patient_qa(patient_id, question)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/patient/{patient_id}/ask", status_code=303)


# ─── GLM 5.1 Trend Detection ────────────────────────────────
@app.post("/patient/{patient_id}/trends")
async def detect_trends(patient_id: str):
    from app.services.glm_service import run_trend_detection

    result = await run_trend_detection(patient_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/patient/{patient_id}", status_code=303)


# ─── GLM 5.1 Encounter Summarization ────────────────────────
@app.post("/encounter/{encounter_id}/summarize")
async def summarize_encounter(encounter_id: str):
    from app.services.glm_service import run_encounter_summary

    result = await run_encounter_summary(encounter_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    with get_db() as db:
        enc = db.execute(
            "SELECT patient_id FROM encounters WHERE id = ?", (encounter_id,)
        ).fetchone()
    return RedirectResponse(f"/patient/{enc['patient_id']}", status_code=303)


# ─── GLM 5.1 Follow-up Suggestions ──────────────────────────
@app.post("/analysis/{analysis_id}/followups")
async def generate_followups(analysis_id: str):
    from app.services.glm_service import run_followup_suggestions

    result = await run_followup_suggestions(analysis_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(f"/analysis/{analysis_id}", status_code=303)


# ─── GLM 5.1 Care Plan Generation ───────────────────────────
@app.post("/patient/{patient_id}/careplan")
async def generate_careplan(patient_id: str):
    from app.services.glm_service import run_careplan_generation

    result = await run_careplan_generation(patient_id)
    if "error" in result:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=400)
    return RedirectResponse(
        f"/patient/{patient_id}/careplan/{result['plan_id']}", status_code=303
    )


@app.get("/patient/{patient_id}/careplan/{plan_id}", response_class=HTMLResponse)
async def view_careplan(request: Request, patient_id: str, plan_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)
        plan = db.execute(
            "SELECT * FROM care_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan:
            return HTMLResponse("<h1>Care plan not found</h1>", status_code=404)
        plan_data = json.loads(plan["plan_json"])

    return templates.TemplateResponse(
        "careplan.html",
        {
            "request": request,
            "patient": dict(patient),
            "plan": plan_data,
            "plan_id": plan_id,
            "raw_response": plan["raw_response"],
            "model": plan["model"],
            "created_at": plan["created_at"],
            "glm_available": bool(os.getenv("GLM_API_KEY")),
        },
    )


# ─── Task Lifecycle ──────────────────────────────────────────
@app.post("/task/{task_id}/complete")
async def complete_task(task_id: str):
    with get_db() as db:
        task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return HTMLResponse("<h1>Task not found</h1>", status_code=404)
        db.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), task_id),
        )
    return RedirectResponse(f"/patient/{task['patient_id']}", status_code=303)


@app.post("/task/{task_id}/skip")
async def skip_task(task_id: str):
    with get_db() as db:
        task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return HTMLResponse("<h1>Task not found</h1>", status_code=404)
        db.execute(
            "UPDATE tasks SET status = 'skipped', completed_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), task_id),
        )
    return RedirectResponse(f"/patient/{task['patient_id']}", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        reload=os.getenv("DEBUG", "true").lower() == "true",
    )
