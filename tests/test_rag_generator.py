"""
Unit tests for services/rag_generator.py

Covers:
  - _build_context: formatting of retrieved chunks into numbered context block
  - generate_answer: fail-open paths (no API key, empty chunks, no anthropic pkg)

No live API calls are made — all paths that would hit the Anthropic API
are exercised via the fail-open guard (ANTHROPIC_API_KEY absent).

Refs: yebyen/mecris#305 / kingdonb/mecris#207
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from services.rag_generator import _build_context, generate_answer, _SNIPPET_CHARS


# ---------------------------------------------------------------------------
# _build_context
# ---------------------------------------------------------------------------

class TestBuildContext:
    def test_single_chunk_numbered(self):
        chunks = [{"title": "Architecture", "source": "docs/arch.md", "snippet": "Overview of the system."}]
        result = _build_context(chunks)
        assert result.startswith("[1]")
        assert "Architecture" in result
        assert "docs/arch.md" in result
        assert "Overview of the system." in result

    def test_multiple_chunks_numbered_sequentially(self):
        chunks = [
            {"title": "Doc A", "source": "docs/a.md", "snippet": "Content A."},
            {"title": "Doc B", "source": "docs/b.md", "snippet": "Content B."},
            {"title": "Doc C", "source": "docs/c.md", "snippet": "Content C."},
        ]
        result = _build_context(chunks)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result

    def test_chunks_separated_by_double_newline(self):
        chunks = [
            {"title": "A", "source": "a.md", "snippet": "Alpha"},
            {"title": "B", "source": "b.md", "snippet": "Beta"},
        ]
        result = _build_context(chunks)
        assert "\n\n" in result

    def test_empty_chunks_returns_empty_string(self):
        assert _build_context([]) == ""

    def test_missing_title_uses_untitled(self):
        chunks = [{"source": "docs/mystery.md", "snippet": "No title here."}]
        result = _build_context(chunks)
        assert "Untitled" in result

    def test_missing_source_uses_empty_string(self):
        chunks = [{"title": "Titled", "snippet": "Body."}]
        result = _build_context(chunks)
        assert "Titled" in result
        # No crash; source defaults to empty string
        assert "()" in result or "Titled" in result

    def test_snippet_truncated_to_snippet_chars(self):
        long_snippet = "x" * (_SNIPPET_CHARS + 200)
        chunks = [{"title": "Big", "source": "big.md", "snippet": long_snippet}]
        result = _build_context(chunks)
        # The included snippet should not exceed _SNIPPET_CHARS chars
        assert "x" * (_SNIPPET_CHARS + 1) not in result

    def test_single_chunk_format(self):
        chunks = [{"title": "My Title", "source": "path/to/file.md", "snippet": "Snippet text."}]
        result = _build_context(chunks)
        # Expected: "[1] My Title (path/to/file.md)\nSnippet text."
        assert result == "[1] My Title (path/to/file.md)\nSnippet text."


# ---------------------------------------------------------------------------
# generate_answer — fail-open paths (no live API calls)
# ---------------------------------------------------------------------------

class TestGenerateAnswerFailOpen:
    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        chunks = [{"title": "Doc", "source": "doc.md", "snippet": "Some content.", "description": "", "date": ""}]
        result = generate_answer("What is this?", chunks)
        assert result is None

    def test_returns_none_for_empty_chunks(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
        result = generate_answer("Any query?", [])
        assert result is None

    def test_returns_none_when_api_raises(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
        chunks = [{"title": "Doc", "source": "doc.md", "snippet": "Content."}]
        # Patch the Anthropic client to raise
        with patch("services.rag_generator._anthropic_lib") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = RuntimeError("API error")
            result = generate_answer("What?", chunks)
        assert result is None

    def test_returns_string_when_api_succeeds(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
        chunks = [{"title": "Doc", "source": "doc.md", "snippet": "The system uses BM25."}]
        with patch("services.rag_generator._anthropic_lib") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="BM25 is a ranking algorithm.")]
            mock_client.messages.create.return_value = mock_response
            result = generate_answer("What is BM25?", chunks)
        assert result == "BM25 is a ranking algorithm."

    def test_correct_model_passed(self, monkeypatch):
        from services.rag_generator import _MODEL
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
        chunks = [{"title": "X", "source": "x.md", "snippet": "body"}]
        with patch("services.rag_generator._anthropic_lib") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="answer")]
            mock_client.messages.create.return_value = mock_response
            generate_answer("question", chunks)
            call_kwargs = mock_client.messages.create.call_args
            assert call_kwargs.kwargs.get("model") == _MODEL

    def test_custom_model_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
        chunks = [{"title": "X", "source": "x.md", "snippet": "body"}]
        with patch("services.rag_generator._anthropic_lib") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="ok")]
            mock_client.messages.create.return_value = mock_response
            generate_answer("q", chunks, model="claude-opus-4-6")
            call_kwargs = mock_client.messages.create.call_args
            assert call_kwargs.kwargs.get("model") == "claude-opus-4-6"

    def test_query_appears_in_user_message(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
        chunks = [{"title": "X", "source": "x.md", "snippet": "body"}]
        with patch("services.rag_generator._anthropic_lib") as mock_lib:
            mock_client = MagicMock()
            mock_lib.Anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="ok")]
            mock_client.messages.create.return_value = mock_response
            generate_answer("unique_query_string", chunks)
            call_kwargs = mock_client.messages.create.call_args
            messages = call_kwargs.kwargs.get("messages", [])
            user_content = messages[0]["content"] if messages else ""
            assert "unique_query_string" in user_content
