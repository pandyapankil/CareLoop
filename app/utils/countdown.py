from datetime import datetime, timedelta, timezone
import re


def _parse_iso(iso_datetime_str: str) -> datetime:
    cleaned = iso_datetime_str.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    cleaned_z = re.sub(r"Z$", "+00:00", cleaned)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            dt = datetime.strptime(cleaned_z, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime string: {iso_datetime_str}")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def format_countdown(iso_datetime_str: str) -> str:
    target = _parse_iso(iso_datetime_str)
    now = _now_utc()
    delta = target - now
    total_seconds = delta.total_seconds()

    if total_seconds < 0:
        overdue = abs(delta)
        days = overdue.days
        hours = overdue.seconds // 3600
        minutes = (overdue.seconds % 3600) // 60
        if days > 0:
            return f"Overdue {days} {'day' if days == 1 else 'days'}"
        if hours > 0:
            return f"Overdue {hours}h"
        return f"Overdue {max(minutes, 1)}m"

    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 3:
        return f"{days} days away"
    if days == 3:
        return "3 days away"
    if days == 2:
        return "2 days away"
    if days == 1:
        time_str = (
            target.strftime("%-I:%M %p")
            if _is_posix()
            else target.strftime("%I:%M %p").lstrip("0")
        )
        return f"Tomorrow at {time_str}"
    if days == 0:
        time_str = (
            target.strftime("%-I:%M %p")
            if _is_posix()
            else target.strftime("%I:%M %p").lstrip("0")
        )
        if total_seconds < 3600:
            return f"{max(int(total_seconds // 60), 1)}m"
        return f"Today at {time_str}"

    return f"{days} days away"


def _is_posix() -> bool:
    import platform

    return platform.system() != "Windows"


def calculate_task_status(due_date_str: str, current_status: str) -> str:
    terminal_statuses = {"completed", "skipped", "canceled"}
    if current_status.lower() in terminal_statuses:
        return current_status.lower()

    target = _parse_iso(due_date_str)
    now = _now_utc()
    delta = target - now
    total_seconds = delta.total_seconds()

    if total_seconds < 0:
        return "overdue"

    days = delta.days

    if days == 0:
        return "due_now"

    if days <= 3:
        return "due_soon"

    if current_status.lower() == "pending":
        return "upcoming"

    return current_status.lower()


def format_relative_time(iso_datetime_str: str) -> str:
    target = _parse_iso(iso_datetime_str)
    now = _now_utc()
    delta = now - target
    total_seconds = delta.total_seconds()

    if total_seconds < 0:
        future_delta = abs(delta)
        return _format_duration(future_delta, prefix="", suffix="from now")

    if total_seconds < 60:
        return "just now"

    return _format_duration(delta, prefix="", suffix="ago")


def _format_duration(delta: timedelta, prefix: str = "", suffix: str = "") -> str:
    total_seconds = abs(delta.total_seconds())
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)

    if days > 0:
        parts = f"{days} {'day' if days == 1 else 'days'}"
        if hours > 0:
            parts += f", {hours} {'hour' if hours == 1 else 'hours'}"
        return f"{prefix}{parts} {suffix}".strip()

    if hours > 0:
        return f"{prefix}{hours} {'hour' if hours == 1 else 'hours'} {suffix}".strip()

    return (
        f"{prefix}{minutes} {'minute' if minutes == 1 else 'minutes'} {suffix}".strip()
    )


def is_overdue(due_date_str: str) -> bool:
    target = _parse_iso(due_date_str)
    now = _now_utc()
    return target < now
