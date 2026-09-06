from pathlib import Path
import os
import uuid

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .ai import generate_response
from .bookings import available_slots, create_booking, list_bookings, service_duration, set_google_event_id, delete_booking
from .calendar import create_google_event, google_enabled
from .security import check_input

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app = FastAPI(title="Business AI Support & Booking Demo")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=12)


class BookingRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(default="", max_length=30)
    service: str = Field(min_length=2, max_length=80)
    start_at: str = Field(min_length=16, max_length=40)
    website: str = Field(default="", max_length=100)


def _session_id(request: Request, response: Response) -> str:
    value = request.cookies.get("booking_session")
    if value and len(value) <= 100:
        return value
    value = str(uuid.uuid4())
    response.set_cookie(
        "booking_session",
        value,
        max_age=86400,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return value


@app.get("/health")
def health():
    return {"status": "ok", "calendar_sync": google_enabled()}


@app.get("/api/availability")
@limiter.limit("30/minute")
def availability(request: Request, date: str, service: str):
    try:
        duration = service_duration(service)
        return {
            "date": date,
            "service": service,
            "duration_minutes": duration,
            "slots": available_slots(date, duration),
            "calendar_sync": google_enabled(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bookings")
@limiter.limit("5/hour")
def book(request: Request, payload: BookingRequest, response: Response):
    if payload.website:
        raise HTTPException(status_code=400, detail="Unable to create that appointment.")

    session_id = _session_id(request, response)
    ip = get_remote_address(request)

    try:
        booking = create_booking(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            service=payload.service,
            start_at=payload.start_at,
            ip=ip,
            session_id=session_id,
        )
        try:
            event_id = create_google_event(booking)
        except Exception:
            delete_booking(booking["id"])
            raise HTTPException(status_code=503, detail="The business calendar is temporarily unavailable. Please try another time.")
        if event_id:
            set_google_event_id(booking["id"], event_id)
            booking["calendar_synced"] = True
        else:
            booking["calendar_synced"] = False
        return booking
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/calendar.ics")
@limiter.limit("10/minute")
def calendar_ics(request: Request):
    events = []
    for booking in list_bookings(250):
        start = booking["start_at"].replace("+00:00", "Z").replace("-", "").replace(":", "")
        end = booking["end_at"].replace("+00:00", "Z").replace("-", "").replace(":", "")
        uid = f"{booking['id']}@ai-booking-demo"
        events.append(
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTART:{start}\r\n"
            f"DTEND:{end}\r\n"
            f"SUMMARY:{booking['service']} — {booking['name']}\r\n"
            "END:VEVENT\r\n"
        )
    body = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//AI Booking System//EN\r\n" + "".join(events) + "END:VCALENDAR\r\n"
    return StreamingResponse(iter([body]), media_type="text/calendar")


@app.get("/api/admin/bookings")
@limiter.limit("30/minute")
def admin_bookings(request: Request):
    expected = os.getenv("ADMIN_TOKEN")
    supplied = request.headers.get("X-Admin-Token")
    if not expected or not supplied or supplied != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"bookings": list_bookings(250)}


@app.post("/api/chat")
@limiter.limit("20/minute")
def chat(request: Request, payload: ChatRequest, response: Response):
    allowed, error = check_input(payload.message)
    if not allowed:
        return {"response": error}

    session_id = _session_id(request, response)
    safe_history = []
    for item in payload.history[-10:]:
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        if len(content) > 4000:
            continue
        safe_history.append({"role": role, "content": content})

    if not safe_history or safe_history[-1].get("content") != payload.message:
        safe_history.append({"role": "user", "content": payload.message})

    try:
        answer = generate_response(
            safe_history,
            ip=get_remote_address(request),
            session_id=session_id,
        )
        if not answer:
            raise HTTPException(status_code=500, detail="Empty AI response.")
        return {"response": answer}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to process the request.")


BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
