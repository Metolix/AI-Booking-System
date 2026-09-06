from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .calendar import google_busy, google_enabled

TZ = ZoneInfo("America/Toronto")

SERVICES = {
    "women's haircut": 45,
    "men's haircut": 30,
    "children's haircut": 30,
    "blowout": 45,
    "full colour": 120,
    "full color": 120,
    "highlights": 150,
    "balayage": 180,
    "hair treatment": 45,
    "bridal styling": 120,
}

HOURS = {
    0: (9, 19),
    1: (9, 19),
    2: (9, 19),
    3: (9, 20),
    4: (9, 20),
    5: (10, 18),
}

MAX_DAYS_AHEAD = 60


def clean_text(value: str, max_len: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_len]


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))


def valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15


def service_duration(service: str) -> int:
    key = clean_text(service, 80).lower()
    if key not in SERVICES:
        raise ValueError("That service is not available for booking.")
    return SERVICES[key]


def _parse_local(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def _is_open(start: datetime, end: datetime) -> bool:
    hours = HOURS.get(start.weekday())
    if not hours or start.date() != end.date():
        return False
    opening, closing = hours
    open_at = start.replace(hour=opening, minute=0, second=0, microsecond=0)
    close_at = start.replace(hour=closing, minute=0, second=0, microsecond=0)
    return start >= open_at and end <= close_at


def _conflicts(start: datetime, end: datetime) -> bool:
    return any(start < busy_end and end > busy_start for busy_start, busy_end in google_busy(start, end))


def available_slots(date_text: str, duration: int) -> list[str]:
    if not google_enabled():
        raise ValueError("The business calendar is not connected right now, so appointments cannot be checked or booked.")

    try:
        day = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Use a date in YYYY-MM-DD format.")

    now = datetime.now(TZ)
    if day < now.date() or day > now.date() + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError("Bookings are available only within the next 60 days.")

    hours = HOURS.get(day.weekday())
    if not hours:
        return []

    cursor = datetime(day.year, day.month, day.day, hours[0], 0, tzinfo=TZ)
    closing = cursor.replace(hour=hours[1])
    busy = google_busy(cursor, closing)
    slots = []

    while cursor + timedelta(minutes=duration) <= closing:
        end = cursor + timedelta(minutes=duration)
        if cursor > now and not any(cursor < busy_end and end > busy_start for busy_start, busy_end in busy):
            slots.append(cursor.isoformat())
        cursor += timedelta(minutes=15)

    return slots


def validate_booking(*, name: str, email: str, phone: str, service: str, start_at: str) -> dict:
    if not google_enabled():
        raise ValueError("The business calendar is not connected right now, so no appointment can be created.")

    name = clean_text(name, 100)
    email = clean_text(email, 254).lower()
    phone = clean_text(phone, 30)
    service = clean_text(service, 80)

    if not (2 <= len(name) <= 100):
        raise ValueError("Please provide a valid name.")
    if not valid_email(email):
        raise ValueError("Please provide a valid email address.")
    if not valid_phone(phone):
        raise ValueError("Please provide a valid phone number.")

    duration = service_duration(service)
    start = _parse_local(start_at)
    end = start + timedelta(minutes=duration)
    now = datetime.now(TZ)

    if start <= now:
        raise ValueError("That appointment time has already passed.")
    if start > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError("Bookings are available only within the next 60 days.")
    if start.minute % 15 != 0 or start.second != 0:
        raise ValueError("Appointments must start on a 15-minute interval.")
    if not _is_open(start, end):
        raise ValueError("That time is outside the business hours.")
    if _conflicts(start, end):
        raise ValueError("That time is already booked or unavailable. Please choose another time.")

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "service": service,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }
