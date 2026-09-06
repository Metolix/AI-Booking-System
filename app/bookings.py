from __future__ import annotations

import hashlib
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "bookings.db"
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
MAX_ACTIVE_PER_EMAIL = 3
MAX_ACTIVE_PER_IP = 5


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                service TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                ip_hash TEXT NOT NULL,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL,
                google_event_id TEXT,
                UNIQUE(start_at, status)
            );
            CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(email);
            CREATE INDEX IF NOT EXISTS idx_bookings_ip ON bookings(ip_hash);
            CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_at);
            """
        )


def normalize_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))


def clean_text(value: str, max_len: int) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:max_len]


def ip_hash(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def service_duration(service: str) -> int:
    key = clean_text(service, 80).lower()
    if key not in SERVICES:
        raise ValueError("That service is not available for online booking.")
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


def _active_counts(conn, email: str, iph: str) -> tuple[int, int]:
    now = datetime.now(timezone.utc).isoformat()
    email_count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE email=? AND status='confirmed' AND start_at>?",
        (email, now),
    ).fetchone()[0]
    ip_count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE ip_hash=? AND status='confirmed' AND start_at>?",
        (iph, now),
    ).fetchone()[0]
    return email_count, ip_count


def _google_conflict(start: datetime, end: datetime) -> bool:
    try:
        from .calendar import google_busy, google_enabled
        if not google_enabled():
            return False
        return any(
            start < busy_end and end > busy_start
            for busy_start, busy_end in google_busy(start - timedelta(minutes=1), end + timedelta(minutes=1))
        )
    except Exception:
        return False


def available_slots(date_text: str, duration: int = 30) -> list[str]:
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

    duration = max(15, min(duration, 240))
    slots = []
    cursor = datetime(day.year, day.month, day.day, hours[0], 0, tzinfo=TZ)
    closing = cursor.replace(hour=hours[1])

    with _connect() as conn:
        rows = conn.execute(
            "SELECT start_at, end_at FROM bookings WHERE status='confirmed' AND end_at>? AND start_at<?",
            (cursor.astimezone(timezone.utc).isoformat(), closing.astimezone(timezone.utc).isoformat()),
        ).fetchall()

    busy = [(_parse_local(r["start_at"]), _parse_local(r["end_at"])) for r in rows]

    try:
        from .calendar import google_busy, google_enabled
        if google_enabled():
            busy.extend(google_busy(cursor, closing))
    except Exception:
        pass

    while cursor + timedelta(minutes=duration) <= closing:
        end = cursor + timedelta(minutes=duration)
        if cursor > now and not any(cursor < b_end and end > b_start for b_start, b_end in busy):
            slots.append(cursor.strftime("%Y-%m-%dT%H:%M:%S%z"))
        cursor += timedelta(minutes=15)

    return slots


def create_booking(*, name: str, email: str, phone: str, service: str, start_at: str, ip: str, session_id: str) -> dict:
    name = clean_text(name, 100)
    email = normalize_email(email)
    phone = clean_text(phone, 30)
    service = clean_text(service, 80)
    session_id = clean_text(session_id, 100)

    if not (2 <= len(name) <= 100):
        raise ValueError("Please provide a valid name.")
    if not valid_email(email):
        raise ValueError("Please provide a valid email address.")
    if not session_id:
        raise ValueError("A valid booking session is required.")

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
    if _google_conflict(start, end):
        raise ValueError("That time is no longer available. Please choose another slot.")

    iph = ip_hash(ip)
    booking_id = str(uuid.uuid4())
    start_utc = start.astimezone(timezone.utc).isoformat()
    end_utc = end.astimezone(timezone.utc).isoformat()

    with _connect() as conn:
        email_count, ip_count = _active_counts(conn, email, iph)
        if email_count >= MAX_ACTIVE_PER_EMAIL:
            raise ValueError("This email already has the maximum number of upcoming demo appointments.")
        if ip_count >= MAX_ACTIVE_PER_IP:
            raise ValueError("This network has reached the demo appointment limit. Please try again later.")

        duplicate = conn.execute(
            "SELECT id FROM bookings WHERE email=? AND start_at=? AND status='confirmed'",
            (email, start_utc),
        ).fetchone()
        if duplicate:
            raise ValueError("You already have an appointment at that time.")

        try:
            conn.execute(
                "INSERT INTO bookings(id,name,email,phone,service,start_at,end_at,ip_hash,session_id,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    booking_id,
                    name,
                    email,
                    phone,
                    service,
                    start_utc,
                    end_utc,
                    iph,
                    session_id,
                    "confirmed",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except sqlite3.IntegrityError:
            raise ValueError("That time was just booked by someone else. Please choose another slot.")

    return {
        "id": booking_id,
        "name": name,
        "email": email,
        "phone": phone,
        "service": service,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "status": "confirmed",
    }


def set_google_event_id(booking_id: str, event_id: str):
    with _connect() as conn:
        conn.execute("UPDATE bookings SET google_event_id=? WHERE id=?", (event_id, booking_id))


def delete_booking(booking_id: str):
    with _connect() as conn:
        conn.execute("DELETE FROM bookings WHERE id=?", (booking_id,))


def list_bookings(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id,name,email,phone,service,start_at,end_at,status,created_at,google_event_id FROM bookings WHERE status='confirmed' ORDER BY start_at LIMIT ?",
            (min(max(limit, 1), 250),),
        ).fetchall()
    return [dict(row) for row in rows]


init_db()
