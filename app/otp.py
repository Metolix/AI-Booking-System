from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

COOKIE_NAME = "booking_otp"
OTP_TTL_SECONDS = 600
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def _secret() -> bytes:
    value = os.getenv("BOOKING_OTP_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("BOOKING_OTP_SECRET must be configured with at least 32 characters.")
    return value.encode("utf-8")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).digest())


def _encode(data: dict) -> str:
    payload = _b64(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{payload}.{_sign(payload)}"


def _decode(value: str) -> dict:
    try:
        payload, signature = value.split(".", 1)
        expected = _sign(payload)
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        data = json.loads(_unb64(payload).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except Exception as exc:
        raise ValueError("Invalid booking verification session.") from exc


def booking_fingerprint(booking: dict) -> str:
    canonical = "|".join(
        [
            booking["name"],
            booking["email"],
            booking["phone"],
            booking["service"],
            booking["start_at"],
        ]
    )
    return hmac.new(_secret(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def create_challenge(booking: dict) -> tuple[str, int]:
    now = int(time.time())
    otp = f"{secrets.randbelow(1_000_000):06d}"
    fingerprint = booking_fingerprint(booking)
    otp_hash = hmac.new(_secret(), f"otp:{otp}".encode("utf-8"), hashlib.sha256).hexdigest()
    data = {
        "id": secrets.token_urlsafe(18),
        "fp": fingerprint,
        "otp": otp_hash,
        "iat": now,
        "exp": now + OTP_TTL_SECONDS,
        "sent": now,
        "attempts": 0,
    }
    return _encode(data), otp


def read_challenge(cookie_value: str) -> dict:
    data = _decode(cookie_value)
    now = int(time.time())
    if int(data.get("exp", 0)) < now:
        raise ValueError("The verification code has expired. Request a new code.")
    if int(data.get("attempts", MAX_ATTEMPTS)) >= MAX_ATTEMPTS:
        raise ValueError("Too many incorrect verification attempts. Request a new code.")
    return data


def check_resend_allowed(cookie_value: str | None) -> None:
    if not cookie_value:
        return
    try:
        data = _decode(cookie_value)
        if int(time.time()) - int(data.get("sent", 0)) < RESEND_COOLDOWN_SECONDS:
            raise ValueError("Please wait before requesting another verification code.")
    except ValueError as exc:
        if "Please wait" in str(exc):
            raise


def verify_code(data: dict, code: str, booking: dict) -> tuple[bool, dict | None]:
    if data.get("fp") != booking_fingerprint(booking):
        raise ValueError("This verification code does not match the booking details.")

    supplied = str(code).strip()
    if len(supplied) != 6 or not supplied.isdigit():
        raise ValueError("Enter the 6-digit verification code.")

    expected = str(data.get("otp", ""))
    actual = hmac.new(_secret(), f"otp:{supplied}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(actual, expected):
        attempts = int(data.get("attempts", 0)) + 1
        if attempts >= MAX_ATTEMPTS:
            raise ValueError("Too many incorrect verification attempts. Request a new code.")
        updated = {**data, "attempts": attempts}
        raise ValueError(f"Incorrect verification code. {MAX_ATTEMPTS - attempts} attempts remaining.")

    return True, {**data, "verified": True}


def refresh_attempts(data: dict, booking: dict, code: str) -> str:
    try:
        verify_code(data, code, booking)
        return _encode({**data, "verified": True})
    except ValueError as exc:
        if "Incorrect verification code" not in str(exc):
            raise
        attempts = int(data.get("attempts", 0)) + 1
        updated = {**data, "attempts": attempts}
        raise ValueError(str(exc)) from exc
