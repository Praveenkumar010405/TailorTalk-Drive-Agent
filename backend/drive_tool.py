from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Type

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent

load_dotenv(BACKEND_DIR / ".env")

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]

MIME_TYPE_GROUPS = {
    "pdf": ["application/pdf"],
    "document": [
        "application/vnd.google-apps.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ],
    "spreadsheet": [
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    ],
    "presentation": [
        "application/vnd.google-apps.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ],
}

MIME_TYPE_LABELS = {
    "application/pdf": "PDF",
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.spreadsheet": "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.folder": "Folder",
    "application/msword": "Word document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word document",
    "application/vnd.ms-excel": "Excel spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel spreadsheet",
    "application/vnd.ms-powerpoint": "PowerPoint presentation",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint presentation",
    "text/plain": "Text file",
    "text/csv": "CSV file",
}


class DriveSearchInput(BaseModel):
    natural_language_query: str = Field(
        ...,
        min_length=1,
        description="The user's natural language Drive search request.",
    )
    q: Optional[str] = Field(
        default=None,
        description=(
            "Optional Google Drive API files.list q parameter. If omitted, the "
            "tool creates a query from natural_language_query."
        ),
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=25,
        description="Maximum number of Drive files to return.",
    )


def _escape_drive_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _quoted(value: str) -> str:
    return f"'{_escape_drive_value(value)}'"


def _or_group(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return "(" + " or ".join(parts) + ")"


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_range_for_month(query: str, now: datetime) -> Optional[tuple[datetime, datetime]]:
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    lower = query.lower()
    for name, month in months.items():
        if name in lower:
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", lower)
            year = int(year_match.group(1)) if year_match else now.year
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(
                year, month + 1, 1, tzinfo=timezone.utc
            )
            return start, end
    return None


def _date_filter(query: str, now: Optional[datetime] = None) -> Optional[str]:
    now = now or datetime.now(timezone.utc)
    lower = query.lower()
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    if "yesterday" in lower:
        start = today_start - timedelta(days=1)
        end = today_start
    elif "today" in lower:
        start = today_start
        end = today_start + timedelta(days=1)
    elif "last week" in lower or "past week" in lower or "previous week" in lower:
        start = now - timedelta(days=7)
        end = now
    elif "last month" in lower or "past month" in lower:
        start = now - timedelta(days=31)
        end = now
    else:
        month_range = _date_range_for_month(query, now)
        if month_range:
            start, end = month_range

    if not start or not end:
        return None

    if "modified" in lower or "updated" in lower or "changed" in lower:
        field = "modifiedTime"
        return f"{field} >= '{_iso_utc(start)}' and {field} < '{_iso_utc(end)}'"

    if "created" in lower or "uploaded" in lower or "added" in lower:
        field = "createdTime"
        return f"{field} >= '{_iso_utc(start)}' and {field} < '{_iso_utc(end)}'"

    created = f"createdTime >= '{_iso_utc(start)}' and createdTime < '{_iso_utc(end)}'"
    modified = f"modifiedTime >= '{_iso_utc(start)}' and modifiedTime < '{_iso_utc(end)}'"
    return f"(({created}) or ({modified}))"


def _mime_filter(query: str) -> Optional[str]:
    lower = query.lower()
    if re.search(r"\b(pdf|pdfs)\b", lower):
        return "mimeType = 'application/pdf'"
    if re.search(r"\b(image|images|photo|photos|picture|pictures|png|jpg|jpeg)\b", lower):
        return "mimeType contains 'image/'"
    if re.search(r"\b(folder|folders)\b", lower):
        return "mimeType = 'application/vnd.google-apps.folder'"

    for label, mime_types in MIME_TYPE_GROUPS.items():
        if re.search(rf"\b({label}|{label}s)\b", lower):
            return _or_group([f"mimeType = {_quoted(mime_type)}" for mime_type in mime_types])

    return None


def _extract_quoted_text(query: str) -> Optional[str]:
    match = re.search(r'"([^"]+)"|' + r"'([^']+)'", query)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _extract_named_file(query: str) -> Optional[str]:
    match = re.search(
        r"\b(?:named|called|exact(?: file)?(?: name)?|file name)\s+([^\n\r]+)",
        query,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = re.sub(r"\b(from|modified|created|uploaded|updated|last|yesterday|today)\b.*$", "", match.group(1), flags=re.I)
    return value.strip(" .\"'") or None


def _extract_content_phrase(query: str) -> Optional[str]:
    match = re.search(r"\b(?:containing|contains|full text|fulltext)\s+([^\n\r]+)", query, flags=re.IGNORECASE)
    if not match:
        return None
    value = re.sub(r"\b(from|modified|created|uploaded|updated|last|yesterday|today)\b.*$", "", match.group(1), flags=re.I)
    return value.strip(" .\"'") or None


def _important_terms(query: str) -> list[str]:
    lower = query.lower()
    stop_words = {
        "a",
        "an",
        "and",
        "any",
        "containing",
        "contains",
        "created",
        "drive",
        "file",
        "files",
        "find",
        "from",
        "google",
        "in",
        "last",
        "list",
        "me",
        "modified",
        "of",
        "on",
        "or",
        "pdf",
        "pdfs",
        "please",
        "search",
        "show",
        "spreadsheet",
        "spreadsheets",
        "the",
        "updated",
        "with",
        "yesterday",
        "today",
        "week",
        "month",
    }
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", lower)
    return [word for word in words if word not in stop_words][:4]


def build_drive_query(natural_language_query: str, q: Optional[str] = None) -> str:
    parts: list[str] = []
    supplied_q = (q or "").strip()

    if supplied_q:
        parts.append(supplied_q)
    else:
        query = natural_language_query.strip()
        lower = query.lower()
        quoted_text = _extract_quoted_text(query)
        named_file = _extract_named_file(query)
        content_phrase = _extract_content_phrase(query)

        if named_file:
            parts.append(f"name = {_quoted(named_file)}")
        elif quoted_text and ("exact" in lower or "named" in lower or "called" in lower):
            parts.append(f"name = {_quoted(quoted_text)}")
        elif quoted_text:
            parts.append(
                _or_group(
                    [
                        f"name contains {_quoted(quoted_text)}",
                        f"fullText contains {_quoted(quoted_text)}",
                    ]
                )
            )
        elif content_phrase:
            parts.append(f"fullText contains {_quoted(content_phrase)}")
        else:
            terms = _important_terms(query)
            if terms:
                searchable = " ".join(terms)
                if "containing" in lower or "contains" in lower or "full text" in lower:
                    parts.append(f"fullText contains {_quoted(searchable)}")
                else:
                    parts.append(
                        _or_group(
                            [
                                f"name contains {_quoted(searchable)}",
                                f"fullText contains {_quoted(searchable)}",
                            ]
                        )
                    )

        mime_filter = _mime_filter(query)
        if mime_filter:
            parts.append(mime_filter)

        date_filter = _date_filter(query)
        if date_filter:
            parts.append(date_filter)

    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder_id:
        parts.append(f"{_quoted(folder_id)} in parents")

    parts.append("trashed = false")
    return " and ".join(f"({part})" if " or " in part and not part.startswith("(") else part for part in parts)


def _service_account_path() -> Path:
    configured = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not configured:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is not set.")

    path = Path(configured).expanduser()
    if not path.is_absolute():
        cwd_path = Path.cwd() / path
        backend_path = BACKEND_DIR / path
        path = cwd_path if cwd_path.exists() else backend_path

    if not path.exists():
        raise FileNotFoundError(f"Service account file was not found: {path}")

    return path


def _drive_service() -> Any:
    credentials = service_account.Credentials.from_service_account_file(
        str(_service_account_path()),
        scopes=DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _friendly_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "Image"
    return MIME_TYPE_LABELS.get(mime_type, mime_type or "Unknown")


def _format_file(item: dict[str, Any]) -> dict[str, str]:
    return {
        "name": item.get("name", "Untitled"),
        "type": _friendly_type(item.get("mimeType", "")),
        "modified_date": item.get("modifiedTime", ""),
        "link": item.get("webViewLink") or f"https://drive.google.com/file/d/{item.get('id', '')}/view",
    }


class DriveSearchTool(BaseTool):
    name: str = "drive_search"
    description: str = (
        "Search Google Drive files. Always pass natural_language_query with the "
        "user's original search request. Optionally pass q only when you already "
        "have a valid Google Drive API files.list query. Returns file name, file "
        "type, modified date, and link."
    )
    args_schema: Type[BaseModel] = DriveSearchInput

    def _run(
        self,
        natural_language_query: str,
        q: Optional[str] = None,
        max_results: int = 10,
    ) -> str:
        drive_query = build_drive_query(natural_language_query=natural_language_query, q=q)
        attempts = 3
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response = (
                    _drive_service()
                    .files()
                    .list(
                        q=drive_query,
                        pageSize=max_results,
                        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                        orderBy="modifiedTime desc",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                files = [_format_file(item) for item in response.get("files", [])]
                return json.dumps(
                    {
                        "query": drive_query,
                        "count": len(files),
                        "files": files,
                    },
                    indent=2,
                )
            except (HttpError, TimeoutError, ConnectionError) as exc:
                last_error = exc
                if attempt == attempts:
                    break
                time.sleep(0.6 * attempt)

        raise RuntimeError(f"Google Drive search failed after {attempts} attempts: {last_error}")
