import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.middleware.auth import get_request_user_id, get_current_user

router = APIRouter(tags=["settings"])

BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_current_user(request)
    with get_db() as db:
        if not user:
            user_settings = {
                "notification_prefs": {
                    "email": True,
                    "push": True,
                    "appointments": True,
                    "medications": True,
                    "tasks": True,
                    "messages": True,
                },
                "theme": "dark",
            }
            return templates.TemplateResponse(
                "settings.html",
                {
                    "request": request,
                    "user": None,
                    "user_name": "",
                    "user_email": "",
                    "notification_prefs": user_settings["notification_prefs"],
                    "theme": user_settings["theme"],
                },
            )

        settings_row = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user["id"],)
        ).fetchone()
        notification_prefs = (
            json.loads(settings_row["notification_prefs_json"])
            if settings_row
            else {
                "email": True,
                "push": True,
                "appointments": True,
                "medications": True,
                "tasks": True,
                "messages": True,
            }
        )
        theme = settings_row["theme"] if settings_row else "dark"

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "user_name": user["name"],
            "user_email": user["email"],
            "notification_prefs": notification_prefs,
            "theme": theme,
        },
    )


@router.post("/settings/notifications")
async def update_notifications(
    request: Request,
    email: str = Form("off"),
    push: str = Form("off"),
    appointments: str = Form("off"),
    medications: str = Form("off"),
    tasks: str = Form("off"),
    messages: str = Form("off"),
):
    prefs = {
        "email": email == "on",
        "push": push == "on",
        "appointments": appointments == "on",
        "medications": medications == "on",
        "tasks": tasks == "on",
        "messages": messages == "on",
    }

    user_id = get_request_user_id(request)
    if not user_id:
        return RedirectResponse("/settings", status_code=303)

    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE user_settings SET notification_prefs_json = ? WHERE user_id = ?",
                (json.dumps(prefs), user_id),
            )
        else:
            db.execute(
                "INSERT INTO user_settings (id, user_id, notification_prefs_json) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), user_id, json.dumps(prefs)),
            )

    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/profile")
async def update_profile(request: Request, name: str = Form(...)):
    user_id = get_request_user_id(request)
    if not user_id:
        return RedirectResponse("/settings", status_code=303)

    with get_db() as db:
        db.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    return RedirectResponse("/settings", status_code=303)
