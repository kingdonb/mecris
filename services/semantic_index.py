"""services/semantic_index.py — TF-IDF semantic search over Chrome bookmarks.

Provides a lightweight, pure-Python TF-IDF vector index with cosine-similarity
ranking. No external ML dependencies required beyond stdlib + numpy.

Plan: yebyen/mecris#280 / kingdonb/mecris#208
"""

import math
import re
from typing import Any, Dict, List, Optional

from tools.chrome_bookmarks import flatten_bookmarks, load_bookmarks


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric word tokeniser (shared with BM25 in rag_retriever)."""
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())


def _doc_text(bookmark: Dict[str, Any]) -> str:
    """Combine bookmark fields into a single indexable string."""
    return " ".join(filter(None, [
        bookmark.get("title", ""),
        bookmark.get("folder", ""),
        bookmark.get("url", ""),
    ]))


# ---------------------------------------------------------------------------
# TF-IDF index
# ---------------------------------------------------------------------------

class BookmarkIndex:
    """In-memory TF-IDF index over a list of Chrome bookmark dicts.

    Usage::

        index = BookmarkIndex()
        index.fit(flatten_bookmarks(load_bookmarks()))
        results = index.search("python asyncio", top_k=3)
    """

    def __init__(self) -> None:
        self._bookmarks: List[Dict[str, Any]] = []
        self._corpus_tokens: List[List[str]] = []
        self._idf: Dict[str, float] = {}
        self._tfidf_vecs: List[Dict[str, float]] = []
        self._n: int = 0

    # ------------------------------------------------------------------
    def fit(self, bookmarks: List[Dict[str, Any]]) -> None:
        """Build the TF-IDF index from a flattened bookmark list."""
        self._bookmarks = bookmarks
        self._n = len(bookmarks)
        self._corpus_tokens = [_tokenize(_doc_text(b)) for b in bookmarks]

        # Document frequency
        df: Dict[str, int] = {}
        for tokens in self._corpus_tokens:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1

        # IDF (smoothed: log((N+1)/(df+1)) + 1)
        self._idf = {
            term: math.log((self._n + 1) / (freq + 1)) + 1
            for term, freq in df.items()
        }

        # TF-IDF vectors (L2-normalised for cosine similarity)
        self._tfidf_vecs = []
        for tokens in self._corpus_tokens:
            vec = self._tfidf_vec(tokens)
            self._tfidf_vecs.append(vec)

    # ------------------------------------------------------------------
    def _tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute normalised term frequency for a token list."""
        counts: Dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        total = max(len(tokens), 1)
        return {t: c / total for t, c in counts.items()}

    def _tfidf_vec(self, tokens: List[str]) -> Dict[str, float]:
        """Return the L2-normalised TF-IDF vector for *tokens*."""
        tf = self._tf(tokens)
        vec: Dict[str, float] = {}
        for term, tf_val in tf.items():
            idf_val = self._idf.get(term, 0.0)
            vec[term] = tf_val * idf_val

        # L2 normalise
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            vec = {t: v / norm for t, v in vec.items()}
        return vec

    # ------------------------------------------------------------------
    def _cosine(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Cosine similarity between two L2-normalised sparse vectors."""
        # Both vectors are already L2-normalised; dot product == cosine similarity
        dot = 0.0
        for term, a_val in vec_a.items():
            if term in vec_b:
                dot += a_val * vec_b[term]
        return dot

    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Return up to *top_k* bookmarks ranked by TF-IDF cosine similarity.

        Each returned dict is the original bookmark dict with an added
        ``score`` field (float, higher is more relevant).
        Returns an empty list if the index is empty or the query is blank.
        """
        if not query.strip() or self._n == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_vec = self._tfidf_vec(query_tokens)
        if not query_vec:
            return []

        scored = [
            (i, self._cosine(query_vec, doc_vec))
            for i, doc_vec in enumerate(self._tfidf_vecs)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for i, score in scored[:top_k]:
            if score <= 0:
                break
            entry = dict(self._bookmarks[i])
            entry["score"] = round(score, 6)
            results.append(entry)
        return results


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------

def search_bookmarks(
    query: str,
    top_k: int = 3,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Load Chrome bookmarks and return the top-k semantically relevant matches.

    Args:
        query: Natural-language search query.
        top_k: Maximum results to return (default 3).
        path: Optional override for the bookmarks file path (used in tests).

    Returns a dict with:
      - query: the search term used
      - total_bookmarks: total bookmarks in the index
      - match_count: number of results returned (≤ top_k)
      - matches: list of bookmark dicts with an added ``score`` field
      - source: resolved path, or "not found"
    """
    from tools.chrome_bookmarks import _default_bookmarks_path  # noqa: PLC0415

    bookmarks_path = path or _default_bookmarks_path()
    raw = load_bookmarks(bookmarks_path)
    if not raw:
        return {
            "query": query,
            "total_bookmarks": 0,
            "match_count": 0,
            "matches": [],
            "source": "not found",
        }

    all_bookmarks = flatten_bookmarks(raw)
    index = BookmarkIndex()
    index.fit(all_bookmarks)
    matches = index.search(query, top_k=top_k)
    return {
        "query": query,
        "total_bookmarks": len(all_bookmarks),
        "match_count": len(matches),
        "matches": matches,
        "source": bookmarks_path,
    }
