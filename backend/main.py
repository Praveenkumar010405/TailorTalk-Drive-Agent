from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import ask_agent, clear_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tailortalk-drive-agent")

app = FastAPI(
    title="TailorTalk Drive Agent API",
    description="Conversational AI agent for searching Google Drive files.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=120)


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    tool_used: bool


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = ask_agent(user_message=request.message, session_id=request.session_id)
        return ChatResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(
            status_code=500,
            detail="The agent could not complete the request. Check backend logs and environment variables.",
        ) from exc


@app.delete("/sessions/{session_id}", response_model=HealthResponse)
def delete_session(session_id: str) -> HealthResponse:
    clear_session(session_id)
    return HealthResponse(status="cleared")
