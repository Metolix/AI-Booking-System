from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .ai import generate_response
from .bookings import SERVICES, available_slots, validate_booking
from .calendar import create_google_event, google_enabled
from .email import send_confirmation
from .security import check_input

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app = FastAPI(title="Business AI Support & Booking Demo")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=12)


class AvailabilityRequest(BaseModel):
    service: str = Field(min_length=1, max_length=80)
    date: str = Field(min_length=10, max_length=10)


class BookingRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(min_length=7, max_length=30)
    service: str = Field(min_length=1, max_length=80)
    start_at: str = Field(min_length=19, max_length=40)
    website: str = Field(default="", max_length=200)


@app.get("/health")
@limiter.limit("60/minute")
def health(request: Request):
    return {"status": "ok", "google_calendar": google_enabled()}


@app.get("/book")
@limiter.limit("120/minute")
def booking_page(request: Request):
    return FileResponse(Path(__file__).resolve().parent.parent / "static" / "book.html")


@app.get("/api/services")
@limiter.limit("60/minute")
def services(request: Request):
    return {"services": [{"name": name, "duration_minutes": duration} for name, duration in SERVICES.items()]}


@app.post("/api/availability")
@limiter.limit("30/minute")
def availability(request: Request, payload: AvailabilityRequest):
    try:
        from .bookings import service_duration
        duration = service_duration(payload.service)
        slots = available_slots(payload.date, duration)
        return {"service": payload.service, "date": payload.date, "duration_minutes": duration, "slots": slots}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="Availability is temporarily unavailable.")


@app.post("/api/bookings")
@limiter.limit("5/minute")
def create_booking(request: Request, payload: BookingRequest):
    if payload.website.strip():
        raise HTTPException(status_code=400, detail="Unable to process this booking.")

    try:
        booking = validate_booking(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            service=payload.service,
            start_at=payload.start_at,
        )
        event_id = create_google_event(booking)
        if not event_id:
            raise ValueError("The business calendar could not confirm the appointment.")
        confirmed = {**booking, "event_id": event_id, "status": "confirmed"}
        try:
            send_confirmation(booking=confirmed)
            email_sent = True
        except Exception:
            email_sent = False
        return {"status": "confirmed", "booking": booking, "confirmation_email_sent": email_sent}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="The booking could not be completed right now.")


@app.post("/api/chat")
@limiter.limit("20/minute")
def chat(request: Request, payload: ChatRequest):
    allowed, error = check_input(payload.message)
    if not allowed:
        return {"response": error}

    safe_history = []
    for item in payload.history[-10:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and len(content) <= 4000:
            safe_history.append({"role": role, "content": content})

    if not safe_history or safe_history[-1].get("content") != payload.message:
        safe_history.append({"role": "user", "content": payload.message})

    try:
        answer = generate_response(safe_history)
        if not answer:
            raise HTTPException(status_code=500, detail="Empty AI response.")
        return {"response": answer}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to process the request.")


BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
