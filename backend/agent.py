from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from drive_tool import DriveSearchTool
from prompt import SYSTEM_PROMPT

load_dotenv(Path(__file__).resolve().parent / ".env")

MAX_HISTORY_MESSAGES = 12
MAX_TOOL_ROUNDS = 3

_memory: dict[str, list[HumanMessage | AIMessage]] = {}
_tool = DriveSearchTool()


def _session_id(value: Optional[str]) -> str:
    return value.strip() if value and value.strip() else str(uuid.uuid4())


def _gemini_model() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        google_api_key=api_key,
        temperature=0.2,
    )


def _invoke_with_retry(llm: ChatGoogleGenerativeAI, messages: list, attempts: int = 3):
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(0.8 * attempt)
    raise RuntimeError(f"Gemini request failed after {attempts} attempts: {last_error}")


def _looks_like_drive_search(message: str) -> bool:
    lower = message.lower()
    keywords = [
        "drive",
        "file",
        "files",
        "find",
        "folder",
        "image",
        "pdf",
        "report",
        "search",
        "show",
        "spreadsheet",
    ]
    return any(keyword in lower for keyword in keywords)


def _manual_search_summary(message: str) -> str:
    result = _tool.invoke({"natural_language_query": message, "max_results": 10})
    return (
        "I searched Google Drive with the drive_search tool. Summarize these "
        "results naturally, preserving every file name, type, modified date, "
        f"and clickable link:\n\n{result}"
    )


def _drive_tool_args(raw_args: dict | None, fallback_query: str) -> dict:
    args = dict(raw_args or {})
    natural_language_query = args.get("natural_language_query") or args.get("query") or args.get("user_query")

    if not natural_language_query and args.get("q"):
        natural_language_query = args.pop("q")

    if not natural_language_query:
        natural_language_query = fallback_query

    args["natural_language_query"] = str(natural_language_query).strip()
    return args


def ask_agent(user_message: str, session_id: Optional[str] = None) -> dict[str, str | bool]:
    clean_message = user_message.strip()
    if not clean_message:
        raise ValueError("Message cannot be empty.")
    if len(clean_message) > 4000:
        raise ValueError("Message is too long. Please keep it under 4000 characters.")

    active_session_id = _session_id(session_id)
    history = _memory.get(active_session_id, [])
    llm = _gemini_model()
    llm_with_tools = llm.bind_tools([_tool])

    messages = [SystemMessage(content=SYSTEM_PROMPT), *history[-MAX_HISTORY_MESSAGES:], HumanMessage(content=clean_message)]
    final_response = _invoke_with_retry(llm_with_tools, messages)
    tool_used = False

    for _ in range(MAX_TOOL_ROUNDS):
        tool_calls = getattr(final_response, "tool_calls", None) or []
        if not tool_calls:
            break

        tool_used = True
        messages.append(final_response)

        for tool_call in tool_calls:
            if tool_call.get("name") != _tool.name:
                continue
            tool_result = _tool.invoke(_drive_tool_args(tool_call.get("args", {}), clean_message))
            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

        final_response = _invoke_with_retry(llm_with_tools, messages)

    if not tool_used and _looks_like_drive_search(clean_message):
        messages.append(HumanMessage(content=_manual_search_summary(clean_message)))
        final_response = _invoke_with_retry(llm, messages)
        tool_used = True

    answer = str(final_response.content).strip()
    if not answer:
        answer = "I could not produce a response. Please try a more specific Drive search."

    updated_history = [*history, HumanMessage(content=clean_message), AIMessage(content=answer)]
    _memory[active_session_id] = updated_history[-MAX_HISTORY_MESSAGES:]

    return {
        "session_id": active_session_id,
        "answer": answer,
        "tool_used": tool_used,
    }


def clear_session(session_id: str) -> None:
    _memory.pop(session_id, None)
