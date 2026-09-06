from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .ai import generate_response
from .calendar import google_enabled
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
    allow_headers=["Content-Type"],
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


@app.get("/health")
def health():
    return {"status": "ok", "google_calendar": google_enabled()}


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
