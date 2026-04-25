"""tests/test_semantic_index.py — Unit tests for TF-IDF semantic bookmark search.

Covers: _tokenize, _doc_text, BookmarkIndex.fit/search, search_bookmarks.
Toward kingdonb/mecris#208 / yebyen/mecris#280.
"""

import json
import tempfile
import os

import pytest

from services.semantic_index import (
    BookmarkIndex,
    _doc_text,
    _tokenize,
    search_bookmarks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_bookmark(title: str, url: str = "", folder: str = "") -> dict:
    return {"title": title, "url": url, "folder": folder, "date_added": None}


CORPUS = [
    _make_bookmark("Python Tutorial", "https://docs.python.org", "Programming"),
    _make_bookmark("JavaScript Basics", "https://mdn.io", "Programming"),
    _make_bookmark("Machine Learning Guide", "https://ml.org", "AI"),
    _make_bookmark("Dog Agility Training", "https://dogagility.com", "Pets"),
    _make_bookmark("Canine Health Tips", "https://caninevet.org", "Pets"),
    _make_bookmark("GitHub Actions Docs", "https://docs.github.com/actions", "DevOps"),
    _make_bookmark("FastAPI Reference", "https://fastapi.tiangolo.com", "Programming"),
]


@pytest.fixture
def index() -> BookmarkIndex:
    idx = BookmarkIndex()
    idx.fit(CORPUS)
    return idx


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_lowercases(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert _tokenize("foo.bar-baz") == ["foo", "bar", "baz"]

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_numbers_kept(self):
        tokens = _tokenize("Python3 v2")
        assert "python3" in tokens
        assert "v2" in tokens


# ---------------------------------------------------------------------------
# _doc_text
# ---------------------------------------------------------------------------

class TestDocText:
    def test_combines_fields(self):
        bm = _make_bookmark("My Page", "https://example.com", "Work")
        text = _doc_text(bm)
        assert "My Page" in text
        assert "https://example.com" in text
        assert "Work" in text

    def test_empty_fields_skipped(self):
        bm = _make_bookmark("Only Title")
        text = _doc_text(bm)
        assert text.strip() == "Only Title"


# ---------------------------------------------------------------------------
# BookmarkIndex.fit
# ---------------------------------------------------------------------------

class TestBookmarkIndexFit:
    def test_empty_corpus(self):
        idx = BookmarkIndex()
        idx.fit([])
        assert idx._n == 0

    def test_corpus_size(self, index):
        assert index._n == len(CORPUS)

    def test_idf_populated(self, index):
        assert len(index._idf) > 0
        # "python" appears in one doc → should have positive IDF
        assert index._idf.get("python", 0) > 0

    def test_tfidf_vecs_count(self, index):
        assert len(index._tfidf_vecs) == len(CORPUS)

    def test_vecs_l2_normalised(self, index):
        import math
        for vec in index._tfidf_vecs:
            if vec:
                norm = math.sqrt(sum(v * v for v in vec.values()))
                assert abs(norm - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# BookmarkIndex.search — ranking correctness
# ---------------------------------------------------------------------------

class TestBookmarkIndexSearch:
    def test_exact_title_match(self, index):
        results = index.search("python", top_k=1)
        assert len(results) == 1
        assert "Python Tutorial" in results[0]["title"]

    def test_top_result_for_ml_query(self, index):
        results = index.search("machine learning", top_k=3)
        titles = [r["title"] for r in results]
        assert "Machine Learning Guide" == titles[0]

    def test_dog_training_query(self, index):
        results = index.search("dog training", top_k=2)
        titles = [r["title"] for r in results]
        # "dog" and "training" both appear in "Dog Agility Training"
        assert "Dog Agility Training" in titles

    def test_javascript_query(self, index):
        results = index.search("javascript", top_k=1)
        assert results[0]["title"] == "JavaScript Basics"

    def test_devops_github_query(self, index):
        results = index.search("github actions", top_k=2)
        titles = [r["title"] for r in results]
        assert "GitHub Actions Docs" in titles

    def test_score_field_present(self, index):
        results = index.search("python", top_k=3)
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)
            assert r["score"] > 0

    def test_results_descending_score(self, index):
        results = index.search("programming python", top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_query_returns_empty(self, index):
        assert index.search("") == []
        assert index.search("   ") == []

    def test_empty_index_returns_empty(self):
        idx = BookmarkIndex()
        idx.fit([])
        assert idx.search("python") == []

    def test_top_k_respected(self, index):
        results = index.search("python tutorial machine learning", top_k=2)
        assert len(results) <= 2

    def test_no_match_returns_empty(self, index):
        # Query with no tokens in any document
        results = index.search("xyzzy quux frobnitz", top_k=3)
        assert results == []

    def test_url_token_searchable(self, index):
        # "fastapi" appears in both title and URL
        results = index.search("fastapi", top_k=1)
        assert results[0]["title"] == "FastAPI Reference"

    def test_folder_token_searchable(self, index):
        # All "Programming" bookmarks share the folder token
        results = index.search("programming", top_k=5)
        titles = [r["title"] for r in results]
        programming_titles = {"Python Tutorial", "JavaScript Basics", "FastAPI Reference"}
        assert any(t in programming_titles for t in titles)


# ---------------------------------------------------------------------------
# search_bookmarks convenience function
# ---------------------------------------------------------------------------

SAMPLE_BOOKMARKS_JSON = {
    "roots": {
        "bookmark_bar": {
            "type": "folder",
            "name": "Bookmarks bar",
            "children": [
                {
                    "type": "url",
                    "name": "Rust Programming Language",
                    "url": "https://rust-lang.org",
                    "date_added": "13346400000000000",
                },
                {
                    "type": "url",
                    "name": "Python Asyncio Docs",
                    "url": "https://docs.python.org/asyncio",
                    "date_added": "13346400000000001",
                },
                {
                    "type": "url",
                    "name": "Kubernetes Cheatsheet",
                    "url": "https://k8s.io",
                    "date_added": "13346400000000002",
                },
            ],
        },
        "other": {"type": "folder", "name": "Other", "children": []},
        "synced": {"type": "folder", "name": "Mobile", "children": []},
    }
}


@pytest.fixture
def bookmarks_file(tmp_path):
    path = tmp_path / "Bookmarks"
    path.write_text(json.dumps(SAMPLE_BOOKMARKS_JSON), encoding="utf-8")
    return str(path)


class TestSearchBookmarks:
    def test_missing_file_returns_not_found(self):
        result = search_bookmarks("python", path="/tmp/nonexistent_bookmarks_xyz")
        assert result["source"] == "not found"
        assert result["match_count"] == 0
        assert result["matches"] == []
        assert result["query"] == "python"

    def test_returns_correct_structure(self, bookmarks_file):
        result = search_bookmarks("rust", path=bookmarks_file)
        assert "query" in result
        assert "total_bookmarks" in result
        assert "match_count" in result
        assert "matches" in result
        assert "source" in result

    def test_finds_rust(self, bookmarks_file):
        result = search_bookmarks("rust", top_k=1, path=bookmarks_file)
        assert result["match_count"] == 1
        assert result["matches"][0]["title"] == "Rust Programming Language"

    def test_finds_python_asyncio(self, bookmarks_file):
        result = search_bookmarks("python asyncio", top_k=1, path=bookmarks_file)
        assert result["match_count"] == 1
        assert result["matches"][0]["title"] == "Python Asyncio Docs"

    def test_total_bookmarks_count(self, bookmarks_file):
        result = search_bookmarks("kubernetes", path=bookmarks_file)
        assert result["total_bookmarks"] == 3

    def test_score_on_each_match(self, bookmarks_file):
        result = search_bookmarks("rust programming", path=bookmarks_file)
        for match in result["matches"]:
            assert "score" in match
            assert match["score"] > 0

    def test_top_k_default_three(self, bookmarks_file):
        result = search_bookmarks("programming", path=bookmarks_file)
        assert result["match_count"] <= 3

    def test_source_is_path(self, bookmarks_file):
        result = search_bookmarks("rust", path=bookmarks_file)
        assert result["source"] == bookmarks_file
