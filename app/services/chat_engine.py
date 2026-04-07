"""Chat engine with single-pass retrieval, citations, and SSE streaming."""
import json
import time
from typing import AsyncGenerator

from llama_index.core import Settings

from app.config import settings
from app.db.stats_repo import record_interaction
from app.services.retriever import RetrievalResult
from app.services.cost_tracker import count_messages_tokens, count_tokens


# Pricing constants (gpt-4.1-mini)
INPUT_COST_PER_TOKEN = 0.15 / 1_000_000
OUTPUT_COST_PER_TOKEN = 0.60 / 1_000_000

FALLBACK_MESSAGE = (
    "I'm sorry, I couldn't find information about that in the uploaded knowledge base."
)

SYSTEM_PROMPT = """You are a precise assistant answering EXCLUSIVELY from the context provided.

STRICT RULES — never violate:
1. Answer ONLY from the context.
2. If context lacks the answer, respond EXACTLY: "{fallback}"
3. NEVER use external knowledge or general information.
4. NEVER fabricate facts, numbers, dates, policies, or names.
5. Every factual sentence must cite one or more source labels like [S1] or [S2].
6. Partial matches: share what you found, then state what is missing.
""".format(fallback=FALLBACK_MESSAGE)


def _source_label(node, idx: int) -> str:
    metadata = getattr(node, "metadata", {}) or {}
    source_type = metadata.get("source_type", "text")
    if source_type == "pdf":
        page = metadata.get("page_number")
        detail = f"PDF page {page}" if page else "PDF"
    elif source_type == "url":
        detail = metadata.get("source_url", "URL")
    else:
        detail = source_type
    return f"S{idx} | {detail}"


def _keyword_score(query: str, text: str) -> float:
    query_terms = {term for term in query.lower().split() if len(term) > 2}
    if not query_terms:
        return 0.0
    text_lower = text.lower()
    overlap = sum(1 for term in query_terms if term in text_lower)
    return overlap / len(query_terms)


def _rerank_nodes(query: str, retrieval_result: RetrievalResult):
    scored_nodes = []
    for node_with_score in retrieval_result.nodes:
        base_score = node_with_score.score or 0.0
        keyword_bonus = _keyword_score(query, node_with_score.node.text)
        combined = (base_score * 0.7) + (keyword_bonus * 0.3)
        scored_nodes.append((combined, node_with_score))
    scored_nodes.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored_nodes]


def _build_messages(
    user_message: str,
    conversation_history: list[dict],
    reranked_nodes: list,
) -> list[dict]:
    context_blocks = []
    for idx, node_with_score in enumerate(reranked_nodes[: settings.N_RETRIEVAL_RESULTS], start=1):
        label = _source_label(node_with_score.node, idx)
        context_blocks.append(f"[{label}]\n{node_with_score.node.text.strip()}")

    context = "\n\n".join(context_blocks)
    history_lines = []
    for msg in conversation_history or []:
        role = msg["role"].upper()
        history_lines.append(f"{role}: {msg['content']}")

    history_text = "\n".join(history_lines) if history_lines else "No prior conversation."
    user_prompt = (
        f"Conversation history:\n{history_text}\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"User question: {user_message}\n\n"
        "Answer the question using only the retrieved context. Use citations like [S1]."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _build_prompt(messages: list[dict]) -> str:
    return "\n\n".join(
        f"{message['role'].upper()}:\n{message['content']}" for message in messages
    )


async def stream_chat_response(
    bot_id: str,
    user_message: str,
    conversation_history: list[dict],
    retrieval_result: RetrievalResult,
    t_start: float,
) -> AsyncGenerator[str, None]:
    """
    Stream chat response using a single retrieval pass and citation-aware prompting.
    
    Args:
        bot_id: Bot identifier for tenant isolation
        user_message: Current user message
        conversation_history: List of previous messages
        retrieval_result: RetrievalResult with nodes and answerability flag
        t_start: Start timestamp for latency calculation
        
    Yields:
        SSE-formatted JSON strings
    """
    # UNANSWERABLE PATH — similarity below threshold
    if not retrieval_result.is_answerable:
        latency_ms = int((time.monotonic() - t_start) * 1000)
        
        await record_interaction(
            bot_id=bot_id,
            latency_ms=latency_ms,
            input_tokens=count_tokens(user_message),
            output_tokens=count_tokens(FALLBACK_MESSAGE),
            unanswered=True
        )
        
        yield f"data: {json.dumps({'delta': FALLBACK_MESSAGE, 'finish_reason': 'unanswerable', 'grounded': False, 'latency_ms': latency_ms})}\n\n"
        yield "data: [DONE]\n\n"
        return
    
    # ANSWERABLE PATH — use the already retrieved nodes only
    try:
        reranked_nodes = _rerank_nodes(user_message, retrieval_result)
        messages = _build_messages(user_message, conversation_history, reranked_nodes)

        # Count full request cost including system prompt and retrieved context
        input_tokens = count_messages_tokens(messages)
        output_tokens = 0

        prompt = _build_prompt(messages)
        response_stream = await Settings.llm.astream_complete(prompt)
        previous_text = ""

        async for token in response_stream:
            delta = getattr(token, "delta", None)
            if not delta:
                current_text = getattr(token, "text", "") or ""
                if current_text.startswith(previous_text):
                    delta = current_text[len(previous_text):]
                else:
                    delta = current_text
                previous_text = current_text
            if delta:
                output_tokens += count_tokens(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        
        # Calculate metrics
        latency_ms = int((time.monotonic() - t_start) * 1000)
        cost_usd = (input_tokens * INPUT_COST_PER_TOKEN + 
                   output_tokens * OUTPUT_COST_PER_TOKEN)
        
        # Final message with stats
        yield f"data: {json.dumps({'delta': '', 'finish_reason': 'stop', 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cost_usd': round(cost_usd, 8), 'latency_ms': latency_ms, 'grounded': True})}\n\n"
        yield "data: [DONE]\n\n"
        
        # Record interaction
        await record_interaction(
            bot_id=bot_id,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            unanswered=False,
            llm_cost_usd=cost_usd
        )
        
    except Exception as e:
        latency_ms = int((time.monotonic() - t_start) * 1000)
        yield f"data: {json.dumps({'error': str(e), 'finish_reason': 'error'})}\n\n"
        yield "data: [DONE]\n\n"
