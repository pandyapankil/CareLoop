import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.routers.notifications import create_notification

router = APIRouter(tags=["messages"])
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "templates"
)


@router.get("/messages", response_class=HTMLResponse)
async def message_inbox(request: Request):
    with get_db() as db:
        received = db.execute(
            "SELECT m.*, u.name as sender_name FROM messages m JOIN users u ON m.sender_id = u.id WHERE m.receiver_id IN (SELECT id FROM users LIMIT 1) ORDER BY m.created_at DESC"
        ).fetchall()

        sent = db.execute(
            "SELECT m.*, u.name as receiver_name FROM messages m JOIN users u ON m.receiver_id = u.id WHERE m.sender_id IN (SELECT id FROM users LIMIT 1) ORDER BY m.created_at DESC"
        ).fetchall()

        users = db.execute("SELECT id, name, role FROM users ORDER BY name").fetchall()
        patients = db.execute("SELECT id, name FROM patients ORDER BY name").fetchall()

    return templates.TemplateResponse(
        "messages.html",
        {
            "request": request,
            "received": [dict(m) for m in received],
            "sent": [dict(m) for m in sent],
            "users": [dict(u) for u in users],
            "patients": [dict(p) for p in patients],
        },
    )


@router.get("/messages/compose", response_class=HTMLResponse)
async def compose_form(request: Request):
    with get_db() as db:
        users = db.execute("SELECT id, name, role FROM users ORDER BY name").fetchall()
        patients = db.execute("SELECT id, name FROM patients ORDER BY name").fetchall()

    return templates.TemplateResponse(
        "message_compose.html",
        {
            "request": request,
            "users": [dict(u) for u in users],
            "patients": [dict(p) for p in patients],
        },
    )


@router.post("/messages/compose")
async def send_message(
    receiver_id: str = Form(...),
    patient_id: str = Form(""),
    subject: str = Form(...),
    body: str = Form(...),
    urgency: str = Form("normal"),
    category: str = Form("general"),
):
    now = datetime.now(timezone.utc).isoformat()
    message_id = str(uuid.uuid4())

    with get_db() as db:
        sender = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        sender_id = sender["id"] if sender else ""

        db.execute(
            "INSERT INTO messages (id, sender_id, receiver_id, patient_id, subject, body, urgency, category, read, parent_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)",
            (
                message_id,
                sender_id,
                receiver_id,
                patient_id or None,
                subject,
                body,
                urgency,
                category,
                now,
            ),
        )

        create_notification(
            db,
            receiver_id,
            "message_received",
            "New message received",
            subject,
            related_id=message_id,
            related_type="message",
        )

    return RedirectResponse("/messages", status_code=303)


@router.get("/message/{message_id}", response_class=HTMLResponse)
async def message_detail(request: Request, message_id: str):
    with get_db() as db:
        message = db.execute(
            "SELECT m.*, s.name as sender_name, r.name as receiver_name FROM messages m JOIN users s ON m.sender_id = s.id JOIN users r ON m.receiver_id = r.id WHERE m.id = ?",
            (message_id,),
        ).fetchone()
        if not message:
            return HTMLResponse("<h1>Message not found</h1>", status_code=404)

        thread = []
        parent_id = message["parent_id"]
        while parent_id:
            parent = db.execute(
                "SELECT m.*, s.name as sender_name, r.name as receiver_name FROM messages m JOIN users s ON m.sender_id = s.id JOIN users r ON m.receiver_id = r.id WHERE m.id = ?",
                (parent_id,),
            ).fetchone()
            if not parent:
                break
            thread.append(dict(parent))
            parent_id = parent["parent_id"]

        replies = db.execute(
            "SELECT m.*, s.name as sender_name, r.name as receiver_name FROM messages m JOIN users s ON m.sender_id = s.id JOIN users r ON m.receiver_id = r.id WHERE m.parent_id = ? ORDER BY m.created_at",
            (message_id,),
        ).fetchall()

        db.execute("UPDATE messages SET read = 1 WHERE id = ?", (message_id,))

    return templates.TemplateResponse(
        "message_detail.html",
        {
            "request": request,
            "message": dict(message),
            "thread": list(reversed(thread)),
            "replies": [dict(r) for r in replies],
        },
    )


@router.post("/message/{message_id}/reply")
async def reply_message(
    message_id: str,
    body: str = Form(...),
):
    now = datetime.now(timezone.utc).isoformat()
    reply_id = str(uuid.uuid4())

    with get_db() as db:
        original = db.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        if not original:
            return RedirectResponse("/messages", status_code=303)

        sender = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        sender_id = sender["id"] if sender else ""

        db.execute(
            "INSERT INTO messages (id, sender_id, receiver_id, patient_id, subject, body, urgency, category, read, parent_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (
                reply_id,
                sender_id,
                original["sender_id"],
                original.get("patient_id"),
                f"Re: {original['subject']}",
                body,
                original["urgency"],
                original["category"],
                message_id,
                now,
            ),
        )

        create_notification(
            db,
            original["sender_id"],
            "message_received",
            "New reply received",
            body[:100],
            related_id=reply_id,
            related_type="message",
        )

    return RedirectResponse(f"/message/{message_id}", status_code=303)


@router.post("/message/{message_id}/read")
async def mark_message_read(message_id: str):
    with get_db() as db:
        db.execute("UPDATE messages SET read = 1 WHERE id = ?", (message_id,))
    return RedirectResponse("/messages", status_code=303)
