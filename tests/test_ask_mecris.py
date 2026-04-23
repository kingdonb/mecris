"""
tests/test_ask_mecris.py — Unit tests for the ask_mecris MCP tool and BM25 retriever.

Plan: yebyen/mecris#259 / kingdonb/mecris#207
Plan: yebyen/mecris#260 (generation step)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from services.rag_retriever import BM25, RAGRetriever, _parse_frontmatter, _snippet
from services.rag_generator import generate_answer, _build_context


# ---------------------------------------------------------------------------
# BM25 unit tests
# ---------------------------------------------------------------------------

class TestBM25Tokenize:
    def test_lowercase(self):
        bm = BM25()
        assert "hello" in bm.tokenize("Hello World")

    def test_alphanumeric_only(self):
        bm = BM25()
        tokens = bm.tokenize("foo-bar baz_qux 123")
        assert "foo" in tokens
        assert "bar" in tokens
        assert "baz_qux" in tokens
        assert "123" in tokens

    def test_empty_string(self):
        bm = BM25()
        assert bm.tokenize("") == []


class TestBM25Retrieval:
    @pytest.fixture
    def fitted_bm25(self):
        bm = BM25()
        docs = [
            "beeminder goal tracking commitment devices",
            "wasm webassembly rust spin fermyon",
            "python mcp server narrator context",
            "walk dog boris fiona activity physical",
            "rag retrieval augmented generation vector index",
        ]
        bm.fit(docs)
        return bm

    def test_empty_query_returns_empty(self, fitted_bm25):
        assert fitted_bm25.retrieve("") == []
        assert fitted_bm25.retrieve("   ") == []

    def test_whitespace_query_returns_empty(self, fitted_bm25):
        assert fitted_bm25.retrieve("\t\n") == []

    def test_relevant_doc_ranked_first(self, fitted_bm25):
        indices = fitted_bm25.retrieve("wasm rust spin")
        assert len(indices) >= 1
        assert indices[0] == 1  # wasm doc is index 1

    def test_rag_query_ranked_first(self, fitted_bm25):
        indices = fitted_bm25.retrieve("rag retrieval vector")
        assert len(indices) >= 1
        assert indices[0] == 4  # rag doc is index 4

    def test_top_k_respected(self, fitted_bm25):
        indices = fitted_bm25.retrieve("python", top_k=2)
        assert len(indices) <= 2

    def test_no_match_returns_empty(self, fitted_bm25):
        indices = fitted_bm25.retrieve("xyzzy nonexistent token")
        assert indices == []

    def test_unfit_bm25_returns_empty(self):
        bm = BM25()
        assert bm.retrieve("anything") == []

    def test_single_doc_corpus(self):
        bm = BM25()
        bm.fit(["hello world"])
        indices = bm.retrieve("hello")
        assert indices == [0]


# ---------------------------------------------------------------------------
# Front-matter parser tests
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_no_frontmatter(self):
        meta, body = _parse_frontmatter("# Just a heading")
        assert meta == {}
        assert "heading" in body

    def test_valid_frontmatter(self):
        text = '---\ntitle: "My Doc"\ndate: "2026-04-23"\n---\n\n# Content'
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "My Doc"
        assert meta["date"] == "2026-04-23"
        assert "Content" in body

    def test_incomplete_delimiter(self):
        text = "---\ntitle: foo"
        meta, body = _parse_frontmatter(text)
        assert meta == {}

    def test_strips_quotes(self):
        text = "---\ntitle: 'Single'\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "Single"


class TestSnippet:
    def test_truncates_at_max(self):
        long_text = "word " * 200
        result = _snippet(long_text, max_chars=50)
        assert len(result) <= 60  # some slack for whitespace collapse

    def test_collapses_whitespace(self):
        result = _snippet("foo   \n\n  bar")
        assert result == "foo bar"


# ---------------------------------------------------------------------------
# RAGRetriever integration tests (with tmp corpus)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    """Build a minimal docs/ + attic/session-chunks/ structure."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    chunks_dir = tmp_path / "attic" / "session-chunks"
    chunks_dir.mkdir(parents=True)

    (docs_dir / "SETUP_GUIDE.md").write_text(
        '---\ntitle: "Setup Guide"\ndescription: "Installation instructions"\ndate: "2026-01-01"\n---\n\n'
        "Install mecris with uv. Configure NEON_DB_URL in .env.",
        encoding="utf-8",
    )
    (docs_dir / "ARCHITECTURE.md").write_text(
        '---\ntitle: "Architecture"\ndescription: "System design overview"\ndate: "2026-01-02"\n---\n\n'
        "Mecris uses FastMCP, Beeminder, Twilio, and a PostgreSQL Neon database.",
        encoding="utf-8",
    )
    (chunks_dir / "2026-04-22.md").write_text(
        '---\ndate: 2026-04-22\nprimary_activity: "Token Bank implemented"\nentry_count: 1\nsource: session_log.md\n---\n\n'
        "Implemented TokenBankService with psycopg2. 490 tests green.",
        encoding="utf-8",
    )

    return tmp_path


class TestRAGRetriever:
    def test_corpus_loads(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        assert r.corpus_size() == 3  # 2 docs + 1 chunk

    def test_retrieve_empty_query(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        assert r.retrieve("") == []
        assert r.retrieve("   ") == []

    def test_retrieve_doc_result(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        results = r.retrieve("neon database postgresql")
        assert len(results) >= 1
        sources = [res["source"] for res in results]
        assert any("ARCHITECTURE" in s for s in sources)

    def test_retrieve_session_chunk(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        results = r.retrieve("token bank psycopg2")
        assert len(results) >= 1
        types = [res["type"] for res in results]
        assert "session" in types

    def test_result_shape(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        results = r.retrieve("mecris setup install")
        assert len(results) >= 1
        for res in results:
            assert "source" in res
            assert "title" in res
            assert "description" in res
            assert "date" in res
            assert "type" in res
            assert "snippet" in res

    def test_top_k_respected(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        results = r.retrieve("mecris", top_k=1)
        assert len(results) <= 1

    def test_no_match(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        results = r.retrieve("xyzzy zork frobnicate")
        assert results == []

    def test_reset_forces_reload(self, tmp_repo):
        r = RAGRetriever(repo_root=tmp_repo)
        _ = r.corpus_size()
        assert r._loaded is True
        r.reset()
        assert r._loaded is False

    def test_missing_dirs_handled(self, tmp_path):
        r = RAGRetriever(repo_root=tmp_path)  # no docs/ or attic/
        assert r.corpus_size() == 0
        assert r.retrieve("anything") == []


# ---------------------------------------------------------------------------
# ask_mecris MCP tool registration tests (source-level, no heavy imports)
# ---------------------------------------------------------------------------

def test_ask_mecris_registered_in_mcp_server():
    """ask_mecris function definition must exist in mcp_server.py source."""
    mcp_server_path = Path(__file__).parent.parent / "mcp_server.py"
    source = mcp_server_path.read_text(encoding="utf-8")
    assert "def ask_mecris(" in source, "ask_mecris not defined in mcp_server.py"
    assert "@mcp.tool(" in source, "mcp.tool decorator not found near ask_mecris"
    assert "ask_mecris" in source


def test_rag_retriever_registered_in_mcp_server():
    """_rag_retriever module-level instance must be in mcp_server.py source."""
    mcp_server_path = Path(__file__).parent.parent / "mcp_server.py"
    source = mcp_server_path.read_text(encoding="utf-8")
    assert "_rag_retriever = RAGRetriever()" in source
    assert "from services.rag_retriever import RAGRetriever" in source


def test_ask_mecris_empty_query_via_retriever(tmp_repo):
    """empty query to RAGRetriever returns [] — mirrors ask_mecris guard."""
    r = RAGRetriever(repo_root=tmp_repo)
    assert r.retrieve("") == []
    assert r.retrieve("   ") == []


def test_ask_mecris_result_structure_via_retriever(tmp_repo):
    """RAGRetriever returns dicts with all fields ask_mecris will forward."""
    r = RAGRetriever(repo_root=tmp_repo)
    results = r.retrieve("mecris neon database")
    for res in results:
        for field in ("source", "title", "description", "date", "type", "snippet"):
            assert field in res, f"Missing field '{field}' in result"


# ---------------------------------------------------------------------------
# RAG generation tests (services/rag_generator.py)
# ---------------------------------------------------------------------------

_SAMPLE_CHUNKS = [
    {
        "source": "docs/ARCHITECTURE.md",
        "title": "Architecture",
        "description": "System design overview",
        "date": "2026-01-02",
        "type": "doc",
        "snippet": "Mecris uses FastMCP, Beeminder, Twilio, and a PostgreSQL Neon database.",
    },
    {
        "source": "docs/SETUP_GUIDE.md",
        "title": "Setup Guide",
        "description": "Installation instructions",
        "date": "2026-01-01",
        "type": "doc",
        "snippet": "Install mecris with uv. Configure NEON_DB_URL in .env.",
    },
]


class TestBuildContext:
    def test_includes_title_and_snippet(self):
        ctx = _build_context(_SAMPLE_CHUNKS)
        assert "Architecture" in ctx
        assert "FastMCP" in ctx

    def test_numbered_entries(self):
        ctx = _build_context(_SAMPLE_CHUNKS)
        assert "[1]" in ctx
        assert "[2]" in ctx

    def test_empty_chunks_returns_empty(self):
        assert _build_context([]) == ""


class TestGenerateAnswerNoApiKey:
    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = generate_answer("what is mecris?", _SAMPLE_CHUNKS)
        assert result is None

    def test_returns_none_for_empty_chunks(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        result = generate_answer("what is mecris?", [])
        assert result is None


class TestGenerateAnswerMocked:
    def test_returns_answer_string(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_text = MagicMock()
        mock_text.text = "Mecris is a personal accountability system."
        mock_response = MagicMock()
        mock_response.content = [mock_text]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("services.rag_generator._anthropic_lib") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result = generate_answer("what is mecris?", _SAMPLE_CHUNKS)

        assert result == "Mecris is a personal accountability system."

    def test_api_failure_returns_none(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API down")

        with patch("services.rag_generator._anthropic_lib") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result = generate_answer("what is mecris?", _SAMPLE_CHUNKS)

        assert result is None

    def test_model_passed_through(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_text = MagicMock()
        mock_text.text = "answer"
        mock_response = MagicMock()
        mock_response.content = [mock_text]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("services.rag_generator._anthropic_lib") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            generate_answer("q", _SAMPLE_CHUNKS, model="claude-opus-4-6")
            call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-opus-4-6"


def test_ask_mecris_answer_field_in_mcp_server_source():
    """ask_mecris must include 'answer' key in its return dict."""
    mcp_server_path = Path(__file__).parent.parent / "mcp_server.py"
    source = mcp_server_path.read_text(encoding="utf-8")
    assert '"answer": answer' in source or "'answer': answer" in source
    assert "_rag_generate" in source
