from __future__ import annotations

import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")


def _google_service():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
    if not raw or not calendar_id:
        return None, None

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(raw),
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False), calendar_id


def google_enabled() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("GOOGLE_CALENDAR_ID"))


def _event_time(value: dict, is_end: bool) -> datetime | None:
    if value.get("dateTime"):
        dt = datetime.fromisoformat(value["dateTime"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    if value.get("date"):
        day = datetime.fromisoformat(value["date"]).date()
        return datetime.combine(day, time.min, TZ)
    return None


def google_busy(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    service, calendar_id = _google_service()
    if not service:
        raise ValueError("Google Calendar is not configured.")

    response = service.events().list(
        calendarId=calendar_id,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute()

    busy = []
    for event in response.get("items", []):
        event_start = _event_time(event.get("start", {}), False)
        event_end = _event_time(event.get("end", {}), True)
        if event_start and event_end:
            busy.append((event_start, event_end))
    return busy


def create_google_event(booking: dict) -> str | None:
    service, calendar_id = _google_service()
    if not service:
        raise ValueError("Google Calendar is not configured.")

    event = {
        "summary": f"Appointment - {booking['service']}",
        "description": (
            f"Customer Name: {booking['name']}\n"
            f"Customer Email: {booking['email']}\n"
            f"Customer Phone: {booking['phone']}\n"
            f"Service: {booking['service']}\n"
            f"Duration: {booking['duration_minutes']} minutes\n"
            f"Start: {booking['start_at']}\n"
            f"End: {booking['end_at']}"
        ),
        "start": {"dateTime": booking["start_at"], "timeZone": "America/Toronto"},
        "end": {"dateTime": booking["end_at"], "timeZone": "America/Toronto"},
        "attendees": [{"email": booking["email"]}],
    }
    created = service.events().insert(calendarId=calendar_id, body=event, sendUpdates="all").execute()
    return created.get("id")
