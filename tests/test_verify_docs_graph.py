"""
Unit tests for scripts/verify_docs_graph.py

Covers:
  - collect_docs
  - _strip_code_blocks
  - extract_links
  - resolve_link
  - build_graph
  - main (CLI)
"""
import json
import sys
from pathlib import Path

import pytest

# The script lives in scripts/ — import via sys.path manipulation
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from verify_docs_graph import (
    _strip_code_blocks,
    build_graph,
    collect_docs,
    extract_links,
    main,
    resolve_link,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# collect_docs
# ---------------------------------------------------------------------------

class TestCollectDocs:
    def test_finds_md_files(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "# A")
        _write(docs / "sub" / "b.md", "# B")
        _write(docs / "ignore.txt", "not a doc")
        result = collect_docs(docs)
        names = {p.name for p in result}
        assert "a.md" in names
        assert "b.md" in names
        assert "ignore.txt" not in names

    def test_returns_sorted(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "z.md", "")
        _write(docs / "a.md", "")
        result = collect_docs(docs)
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_empty_dir_returns_empty(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        assert collect_docs(docs) == []


# ---------------------------------------------------------------------------
# _strip_code_blocks
# ---------------------------------------------------------------------------

class TestStripCodeBlocks:
    def test_removes_fenced_block(self):
        text = "before\n```\n[link](foo.md)\n```\nafter"
        result = _strip_code_blocks(text)
        assert "[link](foo.md)" not in result
        assert "before" in result
        assert "after" in result

    def test_removes_inline_code(self):
        text = "see `[link](foo.md)` here"
        result = _strip_code_blocks(text)
        assert "[link](foo.md)" not in result
        assert "see" in result

    def test_preserves_normal_text(self):
        text = "Hello [world](docs/world.md) end"
        result = _strip_code_blocks(text)
        assert "[world](docs/world.md)" in result

    def test_empty_string(self):
        assert _strip_code_blocks("") == ""


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------

class TestExtractLinks:
    def test_extracts_markdown_links(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[page](page.md)\n")
        links = extract_links(f, docs)
        assert len(links) == 1
        assert links[0].target == "page.md"

    def test_skips_external_urls(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[ext](https://example.com)\n")
        assert extract_links(f, docs) == []

    def test_skips_mailto(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[mail](mailto:test@test.com)\n")
        assert extract_links(f, docs) == []

    def test_skips_anchor_only(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[sec](#section)\n")
        assert extract_links(f, docs) == []

    def test_strips_anchor_fragment(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[p](page.md#section)\n")
        links = extract_links(f, docs)
        assert links[0].target == "page.md"

    def test_extracts_wikilinks(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[[MyPage]]\n")
        links = extract_links(f, docs)
        assert len(links) == 1
        assert links[0].target == "MyPage"

    def test_wikilink_with_alias(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[[MyPage|Display Text]]\n")
        links = extract_links(f, docs)
        assert len(links) == 1
        assert links[0].target == "MyPage"

    def test_skips_links_inside_fenced_code(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "```\n[link](foo.md)\n```\n")
        assert extract_links(f, docs) == []

    def test_returns_empty_for_missing_file(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        missing = docs / "ghost.md"
        assert extract_links(missing, docs) == []

    def test_multiple_links(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "index.md", "[a](a.md) [b](b.md) [[C]]\n")
        links = extract_links(f, docs)
        assert len(links) == 3

    def test_source_rel_is_relative(self, tmp_path):
        docs = tmp_path / "docs"
        f = _write(docs / "sub" / "page.md", "[a](a.md)\n")
        links = extract_links(f, docs)
        assert links[0].source.startswith("docs/")


# ---------------------------------------------------------------------------
# resolve_link
# ---------------------------------------------------------------------------

class TestResolveLink:
    def _setup(self, tmp_path):
        """Create a small docs tree and return (docs_dir, all_stems)."""
        docs = tmp_path / "docs"
        _write(docs / "a.md", "")
        _write(docs / "sub" / "b.md", "")
        all_stems = {f.stem: f for f in docs.rglob("*.md")}
        return docs, all_stems

    def test_resolves_relative_path(self, tmp_path):
        docs, all_stems = self._setup(tmp_path)
        source = docs / "index.md"
        result = resolve_link(source, "a.md", docs, all_stems)
        assert result == (docs / "a.md").resolve()

    def test_resolves_with_md_extension_added(self, tmp_path):
        docs, all_stems = self._setup(tmp_path)
        source = docs / "index.md"
        result = resolve_link(source, "a", docs, all_stems)
        assert result == (docs / "a.md").resolve()

    def test_resolves_bare_stem_wikilink(self, tmp_path):
        docs, all_stems = self._setup(tmp_path)
        source = docs / "index.md"
        result = resolve_link(source, "b", docs, all_stems)
        assert result == (docs / "sub" / "b.md").resolve()

    def test_returns_none_for_nonexistent(self, tmp_path):
        docs, all_stems = self._setup(tmp_path)
        source = docs / "index.md"
        result = resolve_link(source, "nonexistent.md", docs, all_stems)
        assert result is None

    def test_resolves_from_repo_root(self, tmp_path):
        docs, all_stems = self._setup(tmp_path)
        # Create a file at repo root level
        root_file = tmp_path / "README.md"
        _write(root_file, "")
        source = docs / "index.md"
        result = resolve_link(source, "README.md", docs, all_stems)
        assert result == root_file.resolve()


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_no_broken_links(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[b](b.md)\n")
        _write(docs / "b.md", "[a](a.md)\n")
        doc_files, inbound, broken = build_graph(docs)
        assert broken == []
        assert len(doc_files) == 2

    def test_detects_broken_link(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[missing](nowhere.md)\n")
        _write(docs / "b.md", "# B\n")
        _, _, broken = build_graph(docs)
        assert len(broken) == 1
        assert broken[0][1] == "nowhere.md"

    def test_counts_inbound_links(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "hub.md", "[a](a.md)\n[b](b.md)\n")
        _write(docs / "a.md", "[hub](hub.md)\n")
        _write(docs / "b.md", "[hub](hub.md)\n")
        _, inbound, _ = build_graph(docs)
        hub_key = "docs/hub.md"
        assert len(inbound[hub_key]) == 2

    def test_orphaned_doc_has_empty_inbound(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "lonely.md", "# Lonely\n")
        _write(docs / "other.md", "# Other\n")
        _, inbound, _ = build_graph(docs)
        lonely_key = "docs/lonely.md"
        assert inbound[lonely_key] == set()

    def test_empty_docs_dir(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        doc_files, inbound, broken = build_graph(docs)
        assert doc_files == []
        assert inbound == {}
        assert broken == []


# ---------------------------------------------------------------------------
# main (CLI)
# ---------------------------------------------------------------------------

class TestMain:
    def test_returns_0_clean(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[b](b.md)\n")
        _write(docs / "b.md", "[a](a.md)\n")
        rc = main(["--docs-dir", str(docs)])
        assert rc == 0

    def test_returns_0_with_broken_links(self, tmp_path):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[missing](nowhere.md)\n")
        rc = main(["--docs-dir", str(docs)])
        assert rc == 0  # exits 0 regardless; reports are informational

    def test_returns_1_for_missing_dir(self, tmp_path):
        rc = main(["--docs-dir", str(tmp_path / "nonexistent")])
        assert rc == 1

    def test_json_output(self, tmp_path, capsys):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[broken](nowhere.md)\n")
        rc = main(["--docs-dir", str(docs), "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert "broken_links" in report
        assert "orphaned_docs" in report
        assert "total_docs" in report
        assert report["total_docs"] == 1
        assert len(report["broken_links"]) == 1

    def test_json_no_broken_links(self, tmp_path, capsys):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[b](b.md)\n")
        _write(docs / "b.md", "# B\n")
        main(["--docs-dir", str(docs), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["broken_links"] == []

    def test_human_output_no_broken(self, tmp_path, capsys):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "# A\n")
        main(["--docs-dir", str(docs)])
        captured = capsys.readouterr()
        assert "No broken links" in captured.out

    def test_human_output_with_broken(self, tmp_path, capsys):
        docs = tmp_path / "docs"
        _write(docs / "a.md", "[x](ghost.md)\n")
        main(["--docs-dir", str(docs)])
        captured = capsys.readouterr()
        assert "Broken links" in captured.out
