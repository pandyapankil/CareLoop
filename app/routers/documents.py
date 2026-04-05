import os
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter(tags=["documents"])

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024

CATEGORY_CHOICES = [
    ("lab_report", "Lab Report"),
    ("prescription", "Prescription"),
    ("imaging", "Imaging"),
    ("discharge_summary", "Discharge Summary"),
    ("other", "Other"),
]


@router.get("/patient/{patient_id}/documents", response_class=HTMLResponse)
async def list_documents(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

        documents = db.execute(
            "SELECT * FROM documents WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

    return templates.TemplateResponse(
        "documents.html",
        {
            "request": request,
            "patient": dict(patient),
            "documents": [dict(d) for d in documents],
            "categories": CATEGORY_CHOICES,
        },
    )


@router.get("/patient/{patient_id}/documents/upload", response_class=HTMLResponse)
async def upload_document_form(request: Request, patient_id: str):
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    return templates.TemplateResponse(
        "document_upload.html",
        {
            "request": request,
            "patient": dict(patient),
            "categories": CATEGORY_CHOICES,
        },
    )


@router.post("/patient/{patient_id}/documents/upload")
async def upload_document(
    patient_id: str,
    description: str = Form(""),
    category: str = Form("other"),
    file: UploadFile = File(...),
):
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return HTMLResponse(f"<h1>File type {ext} not allowed</h1>", status_code=400)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        return HTMLResponse("<h1>File exceeds 10MB limit</h1>", status_code=400)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / stored_name
    with open(dest, "wb") as f:
        f.write(contents)

    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            "INSERT INTO documents (id, patient_id, uploaded_by, filename, original_filename, file_type, file_size, description, category, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                patient_id,
                "system",
                stored_name,
                file.filename,
                ext,
                len(contents),
                description,
                category,
                "pending",
                now,
            ),
        )

    return RedirectResponse(f"/patient/{patient_id}/documents", status_code=303)


@router.get("/document/{document_id}", response_class=HTMLResponse)
async def document_detail(request: Request, document_id: str):
    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if not doc:
            return HTMLResponse("<h1>Document not found</h1>", status_code=404)

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (doc["patient_id"],)
        ).fetchone()

        reviewer = None
        if doc["reviewed_by"]:
            reviewer = db.execute(
                "SELECT * FROM users WHERE id = ?", (doc["reviewed_by"],)
            ).fetchone()

    return templates.TemplateResponse(
        "document_detail.html",
        {
            "request": request,
            "document": dict(doc),
            "patient": dict(patient) if patient else None,
            "reviewer": dict(reviewer) if reviewer else None,
        },
    )


@router.post("/document/{document_id}/review")
async def review_document(
    document_id: str,
    action: str = Form(...),
    notes: str = Form(""),
):
    status = "reviewed" if action == "approve" else "rejected"
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if not doc:
            return HTMLResponse("<h1>Document not found</h1>", status_code=404)

        db.execute(
            "UPDATE documents SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
            (status, "provider", now, document_id),
        )

    return RedirectResponse(f"/document/{document_id}", status_code=303)


@router.get("/document/{document_id}/download")
async def download_document(document_id: str):
    from fastapi.responses import FileResponse

    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if not doc:
            return HTMLResponse("<h1>Document not found</h1>", status_code=404)

    file_path = UPLOAD_DIR / doc["filename"]
    if not file_path.exists():
        return HTMLResponse("<h1>File not found on disk</h1>", status_code=404)

    return FileResponse(
        file_path,
        filename=doc["original_filename"],
        media_type="application/octet-stream",
    )
