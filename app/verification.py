from __future__ import annotations

import hashlib
import secrets
import threading
import time

from .bookings import validate_booking
from .email import send_confirmation, send_verification_code

CODE_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 5
CODE_PEPPER = secrets.token_bytes(32)
_lock = threading.Lock()
_pending: dict[str, dict] = {}


def _fingerprint(booking: dict) -> str:
    raw = "|".join(
        str(booking[key])
        for key in ("name", "email", "phone", "service", "start_at")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_code(code: str) -> str:
    return hashlib.sha256(CODE_PEPPER + code.encode("utf-8")).hexdigest()


def request_verification(*, name: str, email: str, phone: str, service: str, start_at: str) -> dict:
    booking = validate_booking(
        name=name,
        email=email,
        phone=phone,
        service=service,
        start_at=start_at,
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = time.time()
    fingerprint = _fingerprint(booking)

    with _lock:
        for key, item in list(_pending.items()):
            if item["expires_at"] <= now:
                _pending.pop(key, None)
        pending_id = secrets.token_urlsafe(24)
        _pending[pending_id] = {
            "booking": booking,
            "fingerprint": fingerprint,
            "code_hash": _hash_code(code),
            "expires_at": now + CODE_TTL_SECONDS,
            "attempts": 0,
        }

    try:
        send_verification_code(to=booking["email"], code=code)
    except Exception:
        with _lock:
            _pending.pop(pending_id, None)
        raise

    return {
        "status": "verification_required",
        "email": booking["email"],
        "expires_in_seconds": CODE_TTL_SECONDS,
    }


def verify_and_book(*, name: str, email: str, phone: str, service: str, start_at: str, code: str) -> dict:
    booking = validate_booking(
        name=name,
        email=email,
        phone=phone,
        service=service,
        start_at=start_at,
    )
    fingerprint = _fingerprint(booking)
    code = str(code or "").strip()
    if len(code) != 6 or not code.isdigit():
        raise ValueError("Please enter the 6-digit verification code sent to your email.")

    selected_id = None
    with _lock:
        now = time.time()
        for key, item in list(_pending.items()):
            if item["expires_at"] <= now:
                _pending.pop(key, None)
                continue
            if item["fingerprint"] != fingerprint:
                continue
            if item["attempts"] >= MAX_ATTEMPTS:
                continue
            item["attempts"] += 1
            if secrets.compare_digest(item["code_hash"], _hash_code(code)):
                selected_id = key
                break

        if selected_id is None:
            raise ValueError("That verification code is invalid, expired, or has too many attempts. No appointment was created.")

        pending = _pending[selected_id]

        from .calendar import create_google_event
        event_id = create_google_event(pending["booking"])
        if not event_id:
            raise ValueError("The business calendar could not confirm the appointment. No appointment was created.")

        _pending.pop(selected_id, None)
        confirmed = {**pending["booking"], "event_id": event_id, "status": "confirmed"}

    try:
        send_confirmation(booking=confirmed)
    except Exception:
        confirmed["confirmation_email_sent"] = False
    else:
        confirmed["confirmation_email_sent"] = True

    return confirmed
