"""
LLM generation step for ask_mecris RAG pipeline.

Takes BM25-retrieved chunks and synthesizes a natural language answer
using the Anthropic SDK (claude-haiku-4-5-20251001). Fail-open: returns
None if ANTHROPIC_API_KEY is unset, the SDK is unavailable, or the
API call raises.

Plan: yebyen/mecris#260 / kingdonb/mecris#207
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import anthropic as _anthropic_lib
except ImportError:  # pragma: no cover
    _anthropic_lib = None  # type: ignore[assignment]

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 512
_SNIPPET_CHARS = 600  # chars per chunk included in context


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a numbered context block."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Untitled")
        source = chunk.get("source", "")
        snippet = chunk.get("snippet", "")[:_SNIPPET_CHARS]
        parts.append(f"[{i}] {title} ({source})\n{snippet}")
    return "\n\n".join(parts)


def generate_answer(
    query: str,
    chunks: List[Dict[str, Any]],
    model: str = _MODEL,
) -> Optional[str]:
    """Synthesize a natural language answer from BM25-retrieved chunks.

    Returns None (fail-open) when:
    - ANTHROPIC_API_KEY is not set
    - anthropic package is not installed
    - API call raises any exception

    Args:
        query:  The original user question.
        chunks: List of result dicts from RAGRetriever.retrieve().
        model:  Claude model ID to use (default: haiku).

    Returns:
        Prose answer string, or None on failure/skip.
    """
    if not chunks:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set — skipping RAG generation")
        return None

    if _anthropic_lib is None:  # pragma: no cover
        logger.warning("anthropic package not installed — skipping RAG generation")
        return None

    context = _build_context(chunks)
    system = (
        "You are Mecris, a personal accountability assistant. "
        "Answer the user's question using ONLY the provided context. "
        "Be concise (2-4 sentences). "
        "If the context does not contain enough information, say so honestly."
    )
    user_message = f"Context:\n{context}\n\nQuestion: {query}"

    try:
        client = _anthropic_lib.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG generation failed: %s", exc)
        return None
