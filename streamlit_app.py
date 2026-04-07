"""Streamlit frontend for EzeeChatBot."""
from __future__ import annotations

import json
import os
from typing import Any

import requests
import streamlit as st


DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def _safe_json_loads(raw_text: str) -> dict[str, Any]:
    if not raw_text.strip():
        return {}
    return json.loads(raw_text)


def _stream_chat(api_base_url: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    answer_parts: list[str] = []
    final_event: dict[str, Any] | None = None

    with requests.post(
        f"{api_base_url.rstrip('/')}/chat",
        json=payload,
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
            if event.get("finish_reason"):
                final_event = event

    return "".join(answer_parts).strip(), final_event


st.set_page_config(page_title="EzeeChatBot UI", page_icon="💬", layout="wide")
st.title("EzeeChatBot")
st.caption("Simple upload, chat, and stats UI for the Task E-1 backend")

with st.sidebar:
    st.header("Connection")
    api_base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL)
    st.markdown(
        "Use this UI with the existing FastAPI backend. "
        "Start the backend first, then upload a source, chat with the returned bot, and inspect stats."
    )

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
                response = requests.post(f"{api_base_url.rstrip('/')}/upload", json=payload, timeout=120)
                if response.ok:
                    data = response.json()
                    st.session_state["bot_id"] = data["bot_id"]
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
                response = requests.post(f"{api_base_url.rstrip('/')}/upload", json=payload, timeout=120)
                if response.ok:
                    data = response.json()
                    st.session_state["bot_id"] = data["bot_id"]
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
                payload = {
                    "source_type": "pdf_url",
                    "pdf_url": pdf_url,
                    "metadata": _safe_json_loads(metadata_text),
                }
                response = requests.post(f"{api_base_url.rstrip('/')}/upload", json=payload, timeout=180)
                if response.ok:
                    data = response.json()
                    st.session_state["bot_id"] = data["bot_id"]
                    st.success("PDF URL ingested successfully.")
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
                        files={
                            "pdf_file": (pdf_file.name, pdf_file.getvalue(), "application/pdf"),
                        },
                        timeout=180,
                    )
                    if response.ok:
                        data = response.json()
                        st.session_state["bot_id"] = data["bot_id"]
                        st.success("PDF uploaded successfully.")
                        st.json(data)
                    else:
                        st.error(response.text)
                except Exception as exc:
                    st.error(str(exc))

with tab_chat:
    st.subheader("Chat with a Bot")
    bot_id = st.text_input("Bot ID", value=st.session_state.get("bot_id", ""))
    user_message = st.text_area("Ask a question", height=140, placeholder="What is the refund policy?")
    if st.button("Send Question", type="primary"):
        try:
            answer, final_event = _stream_chat(
                api_base_url,
                {
                    "bot_id": bot_id,
                    "user_message": user_message,
                    "conversation_history": [],
                },
            )
            st.markdown("### Answer")
            st.write(answer or "No answer returned.")
            if final_event:
                st.markdown("### Final Event")
                st.json(final_event)
        except Exception as exc:
            st.error(str(exc))

with tab_stats:
    st.subheader("Bot Statistics")
    stats_bot_id = st.text_input("Bot ID for stats", value=st.session_state.get("bot_id", ""), key="stats_bot_id")
    if st.button("Load Stats"):
        try:
            response = requests.get(f"{api_base_url.rstrip('/')}/stats/{stats_bot_id}", timeout=30)
            if response.ok:
                st.json(response.json())
            else:
                st.error(response.text)
        except Exception as exc:
            st.error(str(exc))
