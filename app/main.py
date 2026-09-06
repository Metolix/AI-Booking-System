from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ai import generate_response
from .security import check_input

app = FastAPI(title="Business AI Support")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    allowed, error = check_input(request.message)

    if not allowed:
        return {
            "response": error
        }

    safe_history = []

    for item in request.history[-10:]:
        role = item.get("role")
        content = item.get("content")

        if role not in ("user", "assistant"):
            continue

        if not isinstance(content, str):
            continue

        if len(content) > 4000:
            continue

        safe_history.append(
            {
                "role": role,
                "content": content
            }
        )

    safe_history.append(
        {
            "role": "user",
            "content": request.message
        }
    )

    try:
        answer = generate_response(safe_history)

        if not answer:
            raise HTTPException(
                status_code=500,
                detail="Empty AI response."
            )

        return {
            "response": answer
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to process the request."
        )


BASE_DIR = Path(__file__).resolve().parent.parent

app.mount(
    "/",
    StaticFiles(
        directory=BASE_DIR / "static",
        html=True
    ),
    name="static"
)