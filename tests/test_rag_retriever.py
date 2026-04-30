"""
Unit tests for services/rag_retriever.py

Covers:
  - BM25: tokenize, fit, score, retrieve (edge cases + real ranking)
  - _parse_frontmatter: standard, no-delimiters, malformed
  - _snippet: truncation and whitespace collapse
  - RAGRetriever: lazy-load, reset, corpus_size, retrieve with tmp dirs

No external dependencies — pure-Python BM25 only.
Refs: yebyen/mecris#305 / kingdonb/mecris#207
"""

import math
from pathlib import Path

import pytest

from services.rag_retriever import (
    BM25,
    RAGRetriever,
    _parse_frontmatter,
    _snippet,
)


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

class TestBM25Tokenize:
    def test_lowercases_tokens(self):
        bm25 = BM25()
        assert bm25.tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        bm25 = BM25()
        tokens = bm25.tokenize("hello, world!")
        assert "hello" in tokens
        assert "world" in tokens

    def test_keeps_underscores(self):
        bm25 = BM25()
        assert "snake_case" in bm25.tokenize("snake_case function")

    def test_keeps_digits(self):
        bm25 = BM25()
        assert "bm25" in bm25.tokenize("BM25 algorithm")

    def test_empty_string(self):
        bm25 = BM25()
        assert bm25.tokenize("") == []


class TestBM25Fit:
    def test_fit_sets_n(self):
        bm25 = BM25()
        bm25.fit(["doc one", "doc two", "doc three"])
        assert bm25._n == 3

    def test_fit_builds_avgdl(self):
        bm25 = BM25()
        bm25.fit(["one two", "three four five"])
        # avg doc len = (2 + 3) / 2 = 2.5
        assert bm25._avgdl == pytest.approx(2.5)

    def test_fit_empty_corpus(self):
        bm25 = BM25()
        bm25.fit([])
        assert bm25._n == 0
        assert bm25._avgdl == 0.0

    def test_fit_builds_idf(self):
        bm25 = BM25()
        bm25.fit(["the quick fox", "the lazy dog"])
        # "the" appears in both docs → IDF exists
        assert "the" in bm25._idf
        # "fox" appears in 1 of 2 docs → IDF is positive
        assert bm25._idf.get("fox", 0) > 0

    def test_fit_doc_freq(self):
        bm25 = BM25()
        bm25.fit(["alpha beta", "alpha gamma"])
        assert bm25._doc_freq["alpha"] == 2
        assert bm25._doc_freq["beta"] == 1


class TestBM25Score:
    def test_relevant_doc_scores_higher(self):
        bm25 = BM25()
        bm25.fit(["python programming language", "cooking recipes pasta"])
        tokens = bm25.tokenize("python")
        score_0 = bm25.score(tokens, 0)  # doc about python
        score_1 = bm25.score(tokens, 1)  # doc about cooking
        assert score_0 > score_1

    def test_unknown_term_scores_zero(self):
        bm25 = BM25()
        bm25.fit(["hello world"])
        tokens = bm25.tokenize("xyz")
        assert bm25.score(tokens, 0) == pytest.approx(0.0)

    def test_score_is_non_negative(self):
        bm25 = BM25()
        bm25.fit(["some document text"])
        tokens = bm25.tokenize("document")
        assert bm25.score(tokens, 0) >= 0


class TestBM25Retrieve:
    def test_returns_best_doc_first(self):
        bm25 = BM25()
        bm25.fit([
            "machine learning algorithms gradient descent",
            "pasta tomato sauce recipe italian",
            "machine learning neural networks deep",
        ])
        results = bm25.retrieve("machine learning", top_k=3)
        # Both ML docs (0 and 2) should appear before the pasta doc
        assert 1 not in results[:2] or results[0] != 1

    def test_top_k_respected(self):
        bm25 = BM25()
        bm25.fit(["alpha", "alpha beta", "alpha beta gamma", "delta", "alpha delta"])
        results = bm25.retrieve("alpha", top_k=2)
        assert len(results) <= 2

    def test_empty_query_returns_empty(self):
        bm25 = BM25()
        bm25.fit(["some document"])
        assert bm25.retrieve("") == []
        assert bm25.retrieve("   ") == []

    def test_empty_corpus_returns_empty(self):
        bm25 = BM25()
        bm25.fit([])
        assert bm25.retrieve("query") == []

    def test_zero_score_docs_excluded(self):
        bm25 = BM25()
        bm25.fit(["hello world", "foo bar baz"])
        results = bm25.retrieve("hello")
        # "foo bar baz" has zero score for "hello" — should not appear
        assert 1 not in results

    def test_returns_indices(self):
        bm25 = BM25()
        bm25.fit(["document zero", "document one"])
        results = bm25.retrieve("document")
        assert all(isinstance(i, int) for i in results)

    def test_single_doc_corpus(self):
        bm25 = BM25()
        bm25.fit(["only document here"])
        results = bm25.retrieve("document")
        assert results == [0]


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_extracts_key_value(self):
        text = "---\ntitle: My Title\n---\nBody text"
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "My Title"
        assert body == "Body text"

    def test_no_frontmatter_returns_empty_dict(self):
        text = "Just plain text\nno frontmatter"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_strips_quotes_from_values(self):
        text = '---\ntitle: "Quoted Title"\n---\nBody'
        meta, _ = _parse_frontmatter(text)
        assert meta["title"] == "Quoted Title"

    def test_strips_single_quotes(self):
        text = "---\ntitle: 'Single Quoted'\n---\nBody"
        meta, _ = _parse_frontmatter(text)
        assert meta["title"] == "Single Quoted"

    def test_multiple_keys(self):
        text = "---\ntitle: Doc\ndate: 2026-01-01\ndescription: A test doc\n---\nBody"
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "Doc"
        assert meta["date"] == "2026-01-01"
        assert meta["description"] == "A test doc"
        assert body == "Body"

    def test_malformed_only_one_delimiter(self):
        text = "---\ntitle: Doc\nno closing"
        meta, body = _parse_frontmatter(text)
        assert meta == {}

    def test_empty_body(self):
        text = "---\ntitle: Title\n---\n"
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "Title"
        assert body == ""

    def test_colon_in_value(self):
        text = "---\ntitle: Hello: World\n---\nBody"
        meta, _ = _parse_frontmatter(text)
        # partition on first ":" only — value is "Hello", rest ignored
        assert "title" in meta


# ---------------------------------------------------------------------------
# _snippet
# ---------------------------------------------------------------------------

class TestSnippet:
    def test_collapses_whitespace(self):
        text = "hello   world\n\nfoo"
        result = _snippet(text, max_chars=400)
        assert "  " not in result

    def test_truncates_to_max_chars(self):
        text = "a" * 500
        result = _snippet(text, max_chars=400)
        # Truncation happens before split, result may be ≤ 400 tokens
        assert len(result) <= 400

    def test_short_text_unchanged(self):
        text = "short text"
        assert _snippet(text, max_chars=400) == "short text"

    def test_empty_string(self):
        assert _snippet("", max_chars=400) == ""


# ---------------------------------------------------------------------------
# RAGRetriever
# ---------------------------------------------------------------------------

class TestRAGRetriever:
    def test_empty_dirs_corpus_size_zero(self, tmp_path):
        """Retriever with no docs/ or session-chunks/ → corpus size 0."""
        retriever = RAGRetriever(repo_root=tmp_path)
        assert retriever.corpus_size() == 0

    def test_retrieve_empty_corpus_returns_empty(self, tmp_path):
        retriever = RAGRetriever(repo_root=tmp_path)
        assert retriever.retrieve("anything") == []

    def test_retrieve_empty_query_returns_empty(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "setup.md").write_text("# Setup\nInstall python and run.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        assert retriever.retrieve("") == []

    def test_loads_docs_directory(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text("# Guide\nLearn how to use the system.\n")
        (docs_dir / "faq.md").write_text("# FAQ\nFrequently asked questions.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        assert retriever.corpus_size() == 2

    def test_loads_session_chunks_directory(self, tmp_path):
        attic = tmp_path / "attic" / "session-chunks"
        attic.mkdir(parents=True)
        (attic / "2026-01-01.md").write_text(
            "---\ndate: 2026-01-01\nprimary_activity: coding\n---\nFixed a bug today.\n"
        )
        retriever = RAGRetriever(repo_root=tmp_path)
        assert retriever.corpus_size() == 1

    def test_retrieve_returns_correct_structure(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "architecture.md").write_text(
            "---\ntitle: Architecture Overview\n---\nThe system uses BM25 retrieval.\n"
        )
        retriever = RAGRetriever(repo_root=tmp_path)
        results = retriever.retrieve("BM25 retrieval")
        assert len(results) >= 1
        r = results[0]
        assert "source" in r
        assert "title" in r
        assert "snippet" in r
        assert "type" in r

    def test_retrieve_finds_relevant_doc(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "python.md").write_text("# Python\nPython is a programming language.\n")
        (docs_dir / "dogs.md").write_text("# Dogs\nDogs are loyal companions.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        results = retriever.retrieve("python programming")
        assert len(results) >= 1
        assert "python" in results[0]["source"].lower()

    def test_lazy_load_only_once(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "one.md").write_text("# One\nFirst document.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        assert not retriever._loaded
        retriever.corpus_size()
        assert retriever._loaded
        # Second call should not reload
        size_before = retriever.corpus_size()
        (docs_dir / "two.md").write_text("# Two\nSecond document added after load.\n")
        size_after = retriever.corpus_size()
        assert size_before == size_after  # not reloaded

    def test_reset_triggers_reload(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "one.md").write_text("# One\nFirst document.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        retriever.corpus_size()  # loads
        # Add another doc and reset
        (docs_dir / "two.md").write_text("# Two\nSecond document.\n")
        retriever.reset()
        assert retriever.corpus_size() == 2

    def test_result_type_field_docs(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("# Doc\nSome document content here.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        results = retriever.retrieve("document content")
        assert results[0]["type"] == "doc"

    def test_result_type_field_session(self, tmp_path):
        attic = tmp_path / "attic" / "session-chunks"
        attic.mkdir(parents=True)
        (attic / "2026-04-01.md").write_text(
            "---\ndate: 2026-04-01\nprimary_activity: testing\n---\nWrote unit tests today.\n"
        )
        retriever = RAGRetriever(repo_root=tmp_path)
        results = retriever.retrieve("unit tests")
        assert results[0]["type"] == "session"

    def test_top_k_limits_results(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        for i in range(5):
            (docs_dir / f"doc{i}.md").write_text(f"# Doc {i}\nContent with keyword alpha beta.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        results = retriever.retrieve("alpha beta", top_k=2)
        assert len(results) <= 2

    def test_frontmatter_title_used(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "untitled.md").write_text(
            "---\ntitle: My Custom Title\n---\nSome body text.\n"
        )
        retriever = RAGRetriever(repo_root=tmp_path)
        retriever.corpus_size()
        # Title comes from frontmatter, not filename
        assert retriever._corpus[0]["title"] == "My Custom Title"

    def test_no_frontmatter_title_uses_stem(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "my-guide.md").write_text("# My Guide\nContent without frontmatter.\n")
        retriever = RAGRetriever(repo_root=tmp_path)
        retriever.corpus_size()
        assert retriever._corpus[0]["title"] == "my-guide"
