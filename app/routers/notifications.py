from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter(tags=["notifications"])
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "templates"
)


def create_notification(
    db,
    user_id: str,
    type: str,
    title: str,
    body: str,
    related_id: Optional[str] = None,
    related_type: Optional[str] = None,
):
    db.execute(
        "INSERT INTO notifications (id, user_id, type, title, body, related_id, related_type, read, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
        (
            str(uuid.uuid4()),
            user_id,
            type,
            title,
            body,
            related_id,
            related_type,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


@router.get("/notifications", response_class=HTMLResponse)
async def notification_list(request: Request):
    with get_db() as db:
        user = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        if not user:
            return HTMLResponse("<h1>No user found</h1>", status_code=404)

        notifications = db.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()

        unread_count = db.execute(
            "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND read = 0",
            (user["id"],),
        ).fetchone()["cnt"]

    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "notifications": [dict(n) for n in notifications],
            "unread_count": unread_count,
        },
    )


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    with get_db() as db:
        db.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
    return RedirectResponse("/notifications", status_code=303)


@router.post("/notifications/read-all")
async def mark_all_read():
    with get_db() as db:
        user = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        if user:
            db.execute(
                "UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0",
                (user["id"],),
            )
    return RedirectResponse("/notifications", status_code=303)


@router.get("/notifications/count")
async def unread_count():
    with get_db() as db:
        user = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        if not user:
            return JSONResponse({"count": 0})
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND read = 0",
            (user["id"],),
        ).fetchone()["cnt"]
    return JSONResponse({"count": count})
