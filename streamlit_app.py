"""Streamlit frontend for EzeeChatBot."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

import requests
import streamlit as st


DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MAX_HISTORY_MESSAGES = 12


def _safe_json_loads(raw_text: str) -> dict[str, Any]:
    if not raw_text.strip():
        return {}
    return json.loads(raw_text)


def _request_headers(api_key: str) -> dict[str, str]:
    headers = {}
    if api_key.strip():
        headers["X-OpenAI-API-Key"] = api_key.strip()
    return headers


def _dedupe_repeated_answer(answer: str) -> str:
    """Collapse exact adjacent duplication in the final assistant answer."""
    text = (answer or "").strip()
    if not text:
        return text

    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    length = len(normalized)
    if length % 2 == 0:
        half = length // 2
        left = normalized[:half].strip()
        right = normalized[half:].strip()
        if left and left == right:
            return left

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if len(paragraphs) >= 2 and len(paragraphs) % 2 == 0:
        half = len(paragraphs) // 2
        if paragraphs[:half] == paragraphs[half:]:
            return "\n\n".join(paragraphs[:half])

    return normalized


def _download_pdf_for_upload(pdf_url: str) -> tuple[str, bytes]:
    response = requests.get(
        pdf_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        },
        allow_redirects=True,
        timeout=45,
    )
    response.raise_for_status()
    pdf_bytes = response.content
    if not pdf_bytes:
        raise ValueError("Downloaded PDF is empty.")
    if not pdf_bytes.startswith(b"%PDF"):
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower():
            raise ValueError("The provided URL did not return a valid PDF file.")

    filename = pdf_url.rstrip("/").split("/")[-1] or "uploaded.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename, pdf_bytes


def _stream_chat(
    api_base_url: str,
    payload: dict[str, Any],
    answer_placeholder,
    api_key: str,
) -> tuple[str, dict[str, Any] | None]:
    answer_parts: list[str] = []
    final_event: dict[str, Any] | None = None

    with requests.post(
        f"{api_base_url.rstrip('/')}/chat",
        json=payload,
        headers=_request_headers(api_key),
        stream=True,
        timeout=120,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            delta = event.get("delta", "")
            if delta:
                answer_parts.append(delta)
                answer_placeholder.markdown("".join(answer_parts))
            if event.get("error"):
                raise RuntimeError(event["error"])
            if event.get("finish_reason"):
                final_event = event

    return "".join(answer_parts).strip(), final_event


def _ensure_chat_state() -> None:
    st.session_state.setdefault("chat_sessions", {})
    st.session_state.setdefault("current_session_id", None)


def _create_chat_session(bot_id: str = "", title: str | None = None) -> str:
    session_id = str(uuid.uuid4())
    st.session_state["chat_sessions"][session_id] = {
        "session_id": session_id,
        "title": title or "New chat",
        "bot_id": bot_id,
        "messages": [],
    }
    st.session_state["current_session_id"] = session_id
    return session_id


def _get_current_session() -> dict[str, Any]:
    _ensure_chat_state()
    current_session_id = st.session_state.get("current_session_id")
    sessions = st.session_state["chat_sessions"]
    if not sessions:
        current_session_id = _create_chat_session(bot_id=st.session_state.get("bot_id", ""))
    elif current_session_id not in sessions:
        current_session_id = next(iter(sessions))
        st.session_state["current_session_id"] = current_session_id
    return sessions[current_session_id]


def _history_payload(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return messages[-MAX_HISTORY_MESSAGES:]


def _sync_current_session_bot(bot_id: str) -> None:
    session = _get_current_session()
    session["bot_id"] = bot_id.strip()


def _label_for_session(session: dict[str, Any]) -> str:
    title = session.get("title") or "New chat"
    bot_id = session.get("bot_id") or "No bot"
    return f"{title} | {bot_id[:8] if bot_id != 'No bot' else bot_id}"


_ensure_chat_state()

st.set_page_config(page_title="EzeeChatBot UI", page_icon="💬", layout="wide")
st.title("EzeeChatBot")
st.caption("Upload a source, create a bot, and chat with session-aware memory from one UI.")

with st.sidebar:
    st.header("Connection")
    api_base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL)
    external_api_key = st.text_input(
        "OpenAI API key override",
        value="",
        type="password",
        help="Optional. If blank, the backend will use its configured environment key/proxy.",
    )
    st.markdown(
        "Use this UI with the existing FastAPI backend. "
        "Upload one source, keep chatting inside a session, and inspect stats."
    )
    if st.button("New chat session"):
        _create_chat_session(bot_id=st.session_state.get("bot_id", ""))
        st.rerun()

tab_upload, tab_chat, tab_stats = st.tabs(["Upload Knowledge Base", "Chat", "Stats"])

with tab_upload:
    st.subheader("Create a Bot from One Source")
    source_mode = st.radio(
        "Choose source type",
        [
            "Plain text",
            "Website URL",
            "PDF URL",
            "PDF file upload",
        ],
        horizontal=True,
    )
    metadata_text = st.text_area("Optional metadata JSON", value="{}", height=100)

    if source_mode == "Plain text":
        text_content = st.text_area("Paste knowledge base text", height=240)
        if st.button("Upload Text", type="primary"):
            try:
                payload = {
                    "source_type": "text",
                    "text_content": text_content,
                    "metadata": _safe_json_loads(metadata_text),
                }
                response = requests.post(
                    f"{api_base_url.rstrip('/')}/upload",
                    json=payload,
                    headers=_request_headers(external_api_key),
                    timeout=120,
                )
                if response.ok:
                    data = response.json()
                    st.session_state["bot_id"] = data["bot_id"]
                    session = _get_current_session()
                    session["bot_id"] = data["bot_id"]
                    st.success("Knowledge base uploaded successfully.")
                    st.json(data)
                else:
                    st.error(response.text)
            except Exception as exc:
                st.error(str(exc))

    elif source_mode == "Website URL":
        website_url = st.text_input("Website URL", placeholder="https://example.com/help/refunds")
        if st.button("Upload Website", type="primary"):
            try:
                payload = {
                    "source_type": "website",
                    "website_url": website_url,
                    "metadata": _safe_json_loads(metadata_text),
                }
                response = requests.post(
                    f"{api_base_url.rstrip('/')}/upload",
                    json=payload,
                    headers=_request_headers(external_api_key),
                    timeout=120,
                )
                if response.ok:
                    data = response.json()
                    st.session_state["bot_id"] = data["bot_id"]
                    session = _get_current_session()
                    session["bot_id"] = data["bot_id"]
                    st.success("Website ingested successfully.")
                    st.json(data)
                else:
                    st.error(response.text)
            except Exception as exc:
                st.error(str(exc))

    elif source_mode == "PDF URL":
        pdf_url = st.text_input("PDF URL", placeholder="https://example.com/policies/refund-policy.pdf")
        if st.button("Upload PDF from URL", type="primary"):
            try:
                filename, pdf_bytes = _download_pdf_for_upload(pdf_url)
                response = requests.post(
                    f"{api_base_url.rstrip('/')}/upload",
                    data={
                        "source_type": "pdf_file",
                        "metadata_json": metadata_text,
                    },
                    headers=_request_headers(external_api_key),
                    files={
                        "pdf_file": (filename, pdf_bytes, "application/pdf"),
                    },
                    timeout=180,
                )
                if response.ok:
                    data = response.json()
                    st.session_state["bot_id"] = data["bot_id"]
                    session = _get_current_session()
                    session["bot_id"] = data["bot_id"]
                    st.success("PDF URL downloaded and ingested successfully.")
                    st.json(data)
                else:
                    st.error(response.text)
            except Exception as exc:
                st.error(str(exc))

    else:
        pdf_file = st.file_uploader("Choose a PDF file", type=["pdf"])
        if st.button("Upload PDF File", type="primary"):
            if pdf_file is None:
                st.error("Please choose a PDF file first.")
            else:
                try:
                    response = requests.post(
                        f"{api_base_url.rstrip('/')}/upload",
                        data={
                            "source_type": "pdf_file",
                            "metadata_json": metadata_text,
                        },
                        headers=_request_headers(external_api_key),
                        files={
                            "pdf_file": (pdf_file.name, pdf_file.getvalue(), "application/pdf"),
                        },
                        timeout=180,
                    )
                    if response.ok:
                        data = response.json()
                        st.session_state["bot_id"] = data["bot_id"]
                        session = _get_current_session()
                        session["bot_id"] = data["bot_id"]
                        st.success("PDF uploaded successfully.")
                        st.json(data)
                    else:
                        st.error(response.text)
                except Exception as exc:
                    st.error(str(exc))

with tab_chat:
    st.subheader("Chat with a Bot")
    sessions = st.session_state["chat_sessions"]
    if not sessions:
        _create_chat_session(bot_id=st.session_state.get("bot_id", ""))
        sessions = st.session_state["chat_sessions"]

    session_options = list(sessions.keys())
    selected_session_id = st.selectbox(
        "Session",
        options=session_options,
        format_func=lambda session_id: _label_for_session(sessions[session_id]),
        index=session_options.index(st.session_state.get("current_session_id")) if st.session_state.get("current_session_id") in session_options else 0,
    )
    st.session_state["current_session_id"] = selected_session_id
    session = sessions[selected_session_id]

    chat_bot_id = st.text_input(
        "Bot ID",
        value=session.get("bot_id") or st.session_state.get("bot_id", ""),
        key=f"chat_bot_id_{selected_session_id}",
        help="Each chat session can point to a different bot if you want.",
    )
    _sync_current_session_bot(chat_bot_id)

    col_keep, col_reset = st.columns([1, 1])
    with col_keep:
        if st.button("New session from this bot"):
            _create_chat_session(bot_id=chat_bot_id)
            st.rerun()
    with col_reset:
        if st.button("Clear current session"):
            session["messages"] = []
            st.rerun()

    st.caption(f"Session ID: `{selected_session_id}`")

    chat_messages_container = st.container()
    with chat_messages_container:
        for message in session["messages"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    with st.form(key=f"chat_form_{selected_session_id}", clear_on_submit=True):
        prompt = st.text_area(
            "Message",
            height=100,
            placeholder="Ask something grounded in the uploaded knowledge base",
            label_visibility="collapsed",
        )
        send_message = st.form_submit_button("Send")

    if send_message:
        if not chat_bot_id.strip():
            st.error("Add a bot ID for this session before sending a message.")
        elif not prompt.strip():
            st.error("Please enter a message before sending.")
        else:
            prompt = prompt.strip()
            user_message = {"role": "user", "content": prompt}
            session["messages"].append(user_message)
            if session["title"] == "New chat":
                session["title"] = prompt[:40]

            with chat_messages_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

                history = _history_payload(session["messages"][:-1])
                with st.chat_message("assistant"):
                    answer_placeholder = st.empty()
                    try:
                        answer, final_event = _stream_chat(
                            api_base_url,
                            {
                                "bot_id": chat_bot_id.strip(),
                                "session_id": selected_session_id,
                                "user_message": prompt,
                                "conversation_history": history,
                            },
                            answer_placeholder,
                            external_api_key,
                        )
                        final_answer = _dedupe_repeated_answer(answer or "No answer returned.")
                        answer_placeholder.markdown(final_answer)
                        session["messages"].append({"role": "assistant", "content": final_answer})
                        if final_event:
                            with st.expander("Response metadata"):
                                st.json(final_event)
                    except Exception as exc:
                        answer_placeholder.empty()
                        session["messages"].pop()
                        st.error(str(exc))

with tab_stats:
    st.subheader("Bot Statistics")
    stats_bot_id = st.text_input("Bot ID for stats", value=st.session_state.get("bot_id", ""), key="stats_bot_id")
    if st.button("Load Stats"):
        try:
            response = requests.get(
                f"{api_base_url.rstrip('/')}/stats/{stats_bot_id}",
                headers=_request_headers(external_api_key),
                timeout=30,
            )
            if response.ok:
                st.json(response.json())
            else:
                st.error(response.text)
        except Exception as exc:
            st.error(str(exc))
