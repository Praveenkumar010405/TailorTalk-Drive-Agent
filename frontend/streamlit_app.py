from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

import streamlit as st

DEFAULT_BACKEND_URL = "http://localhost:8000"


def _backend_url() -> str:
    return os.getenv("TAILORTALK_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")


def _post_chat(message: str, session_id: str) -> dict:
    payload = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    request = urllib.request.Request(
        f"{_backend_url()}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        raise RuntimeError(detail) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach the backend at {_backend_url()}. Start FastAPI first."
        ) from exc


st.set_page_config(page_title="TailorTalk Drive Agent", page_icon="T", layout="centered")

st.title("TailorTalk Drive Agent")
st.caption("Chat with your Google Drive folder using natural language.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi. Ask me to find files in Drive, like `Show PDF files modified "
                "yesterday` or `Find reports containing sales`."
            ),
        }
    ]

with st.sidebar:
    st.subheader("Connection")
    st.write(f"Backend: `{_backend_url()}`")
    if st.button("New chat", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = [
            {"role": "assistant", "content": "New chat started. What should I find in Drive?"}
        ]
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Search your Drive files...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching and thinking..."):
            try:
                result = _post_chat(prompt, st.session_state.session_id)
                st.session_state.session_id = result["session_id"]
                answer = result["answer"]
                st.markdown(answer)
            except RuntimeError as exc:
                answer = f"Error: {exc}"
                st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
