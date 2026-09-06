from __future__ import annotations

import json
import os
from datetime import datetime, timedelta


def _google_service():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
    if not raw or not calendar_id:
        return None, None

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False), calendar_id


def google_enabled() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("GOOGLE_CALENDAR_ID"))


def google_busy(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    service, calendar_id = _google_service()
    if not service:
        return []

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
        event_start = event.get("start", {}).get("dateTime")
        event_end = event.get("end", {}).get("dateTime")
        if event_start and event_end:
            busy.append((datetime.fromisoformat(event_start), datetime.fromisoformat(event_end)))
    return busy


def create_google_event(booking: dict) -> str | None:
    service, calendar_id = _google_service()
    if not service:
        return None

    event = {
        "summary": f"{booking['service']} — {booking['name']}",
        "description": (
            "AI Booking System demo appointment.\n"
            f"Booking ID: {booking['id']}\n"
            f"Customer email: {booking['email']}\n"
            f"Customer phone: {booking['phone'] or 'Not provided'}"
        ),
        "start": {"dateTime": booking["start_at"]},
        "end": {"dateTime": booking["end_at"]},
    }

    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    return created.get("id")


def delete_google_event(event_id: str):
    service, calendar_id = _google_service()
    if service and event_id:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
