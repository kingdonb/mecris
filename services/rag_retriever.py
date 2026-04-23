"""
BM25-based retrieval over docs/ and attic/session-chunks/.

Used by the ask_mecris MCP tool. No external ML dependencies required —
pure-Python BM25 with stdlib only.

Plan: yebyen/mecris#259 / kingdonb/mecris#207
"""

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# BM25 core
# ---------------------------------------------------------------------------

class BM25:
    """Okapi BM25 ranking function. Pure Python, no external dependencies."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._corpus: List[List[str]] = []
        self._doc_freq: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._avgdl: float = 0.0
        self._n: int = 0

    # ------------------------------------------------------------------
    def tokenize(self, text: str) -> List[str]:
        """Lowercase word-tokeniser. Returns alphanumeric tokens."""
        return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())

    # ------------------------------------------------------------------
    def fit(self, documents: List[str]) -> None:
        """Index a list of raw text documents."""
        self._corpus = [self.tokenize(doc) for doc in documents]
        self._n = len(self._corpus)
        total_len = sum(len(tok) for tok in self._corpus)
        self._avgdl = total_len / max(self._n, 1)

        self._doc_freq = {}
        for tokens in self._corpus:
            for token in set(tokens):
                self._doc_freq[token] = self._doc_freq.get(token, 0) + 1

        self._idf = {
            term: math.log((self._n - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in self._doc_freq.items()
        }

    # ------------------------------------------------------------------
    def score(self, query_tokens: List[str], doc_idx: int) -> float:
        """BM25 score for one document."""
        doc = self._corpus[doc_idx]
        dl = len(doc)
        tf_map: Dict[str, int] = {}
        for t in doc:
            tf_map[t] = tf_map.get(t, 0) + 1

        total = 0.0
        for term in query_tokens:
            if term not in self._idf:
                continue
            tf = tf_map.get(term, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / max(self._avgdl, 1))
            total += self._idf[term] * numerator / denominator
        return total

    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 5) -> List[int]:
        """Return indices of top_k documents sorted by descending score."""
        if not query.strip() or self._n == 0:
            return []
        tokens = self.tokenize(query)
        if not tokens:
            return []
        scores = [(i, self.score(tokens, i)) for i in range(self._n)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [i for i, s in scores[:top_k] if s > 0]


# ---------------------------------------------------------------------------
# Front-matter parser
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """Extract YAML front-matter and body from a Markdown file.

    Expects the ``---`` delimiter convention.  Returns (metadata_dict, body).
    Metadata values are strings; lists and complex types are not parsed.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text, body = parts[1], parts[2]
    metadata: Dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            metadata[key.strip()] = val.strip().strip('"').strip("'")
    return metadata, body.strip()


# ---------------------------------------------------------------------------
# Corpus loaders
# ---------------------------------------------------------------------------

def _snippet(text: str, max_chars: int = 400) -> str:
    """Return a plain-text snippet (whitespace-collapsed, max_chars)."""
    return " ".join(text[:max_chars].split())


def _load_docs(docs_dir: Path) -> List[Dict[str, Any]]:
    """Load all Markdown files from docs_dir as retrieval corpus entries."""
    chunks: List[Dict[str, Any]] = []
    for path in sorted(docs_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        title = meta.get("title", path.stem)
        description = meta.get("description", "")
        chunks.append(
            {
                "source": str(path.relative_to(docs_dir.parent)),
                "title": title,
                "description": description,
                "date": meta.get("date", ""),
                "type": "doc",
                # Full text used for BM25 indexing only
                "text": f"{title} {description} {body}",
                "snippet": _snippet(body),
            }
        )
    return chunks


def _load_session_chunks(chunks_dir: Path) -> List[Dict[str, Any]]:
    """Load session-chunk Markdown files from attic/session-chunks/."""
    chunks: List[Dict[str, Any]] = []
    for path in sorted(chunks_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        date_str = meta.get("date", path.stem)
        activity = meta.get("primary_activity", "")
        chunks.append(
            {
                "source": f"attic/session-chunks/{path.name}",
                "title": f"Session log {date_str}",
                "description": activity,
                "date": date_str,
                "type": "session",
                "text": f"{activity} {body}",
                "snippet": _snippet(body),
            }
        )
    return chunks


# ---------------------------------------------------------------------------
# Public retriever
# ---------------------------------------------------------------------------

class RAGRetriever:
    """Lazy-loading BM25 retriever over docs/ and attic/session-chunks/.

    The corpus is loaded and indexed on the first call to ``retrieve()``.
    Subsequent calls reuse the index — no re-indexing across the process
    lifetime unless ``reset()`` is called.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        if repo_root is None:
            # Default: two levels up from services/
            repo_root = Path(__file__).parent.parent
        self._docs_dir: Path = repo_root / "docs"
        self._chunks_dir: Path = repo_root / "attic" / "session-chunks"
        self._corpus: List[Dict[str, Any]] = []
        self._bm25: BM25 = BM25()
        self._loaded: bool = False

    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        corpus: List[Dict[str, Any]] = []
        if self._docs_dir.exists():
            corpus.extend(_load_docs(self._docs_dir))
        if self._chunks_dir.exists():
            corpus.extend(_load_session_chunks(self._chunks_dir))
        self._corpus = corpus
        self._bm25.fit([c["text"] for c in corpus])
        self._loaded = True

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Force re-index on next retrieve() call (e.g. after new docs added)."""
        self._loaded = False
        self._corpus = []
        self._bm25 = BM25()

    # ------------------------------------------------------------------
    def corpus_size(self) -> int:
        """Number of indexed documents (triggers load if not yet done)."""
        self._ensure_loaded()
        return len(self._corpus)

    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return up to top_k most relevant corpus entries for *query*.

        Each result dict contains:
          source, title, description, date, type, snippet
        """
        if not query.strip():
            return []
        self._ensure_loaded()
        indices = self._bm25.retrieve(query, top_k)
        return [
            {
                "source": self._corpus[i]["source"],
                "title": self._corpus[i]["title"],
                "description": self._corpus[i]["description"],
                "date": self._corpus[i]["date"],
                "type": self._corpus[i]["type"],
                "snippet": self._corpus[i]["snippet"],
            }
            for i in indices
        ]
