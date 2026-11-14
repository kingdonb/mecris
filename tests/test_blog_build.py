"""Tests for the blog static site generator (blog/build.py)."""

import importlib.util
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("markdown")

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("blog_build", REPO / "blog" / "build.py")
blog = importlib.util.module_from_spec(_spec)
import sys
sys.modules["blog_build"] = blog  # dataclasses needs the module registered
_spec.loader.exec_module(blog)

POST = """# A Title With `code`

**Date:** 1999-01-01
**Author:** Someone & Kingdon
**Tags:** [a, b]

---

First paragraph with a [link](https://example.test) and **bold**:
1. a list item that is not summary

## Section

```
not a summary
```
"""


def test_parse_post_reads_title_metadata_and_body():
    post = blog.parse_post("2026-11-13-hello-world.md", POST)
    assert post.title == "A Title With code"
    assert post.day == date(2026, 11, 13)  # the filename wins over **Date:**
    assert post.author == "Someone & Kingdon"
    assert post.meta["tags"] == "[a, b]"
    assert post.body.startswith("First paragraph")
    assert post.path == "posts/2026-11-13-hello-world/"


def test_summary_is_first_prose_paragraph_without_markup_or_list():
    post = blog.parse_post("2026-11-13-hello-world.md", POST)
    assert post.summary == "First paragraph with a link and bold:"


def test_explicit_summary_wins():
    post = blog.parse_post("2026-11-13-x.md", "# T\n\n**Summary:** Short and chosen.\n\nBody text.\n")
    assert post.summary == "Short and chosen."


@pytest.mark.parametrize("name", ["notes.md", "2026-1-1-x.md", "2026-11-13-Bad_Slug.md"])
def test_bad_filename_is_rejected(name):
    with pytest.raises(ValueError):
        blog.parse_post(name, POST)


def test_post_without_title_is_rejected():
    with pytest.raises(ValueError):
        blog.parse_post("2026-11-13-x.md", "No heading here.\n")


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def test_drafts_are_excluded_unless_requested(tmp_path):
    _write(tmp_path, "2026-11-12-published.md", "# Published\n\nBody.\n")
    _write(tmp_path, "2026-11-13-held.md", "# Held\n\n**Status:** draft\n\nBody.\n")
    _write(tmp_path, "README.md", "# not a post\n")
    assert [p.slug for p in blog.load_posts(tmp_path)] == ["published"]
    assert [p.slug for p in blog.load_posts(tmp_path, drafts=True)] == ["held", "published"]


def test_build_writes_index_posts_and_valid_feed(tmp_path):
    src, out = tmp_path / "src", tmp_path / "site"
    src.mkdir()
    _write(src, "2026-11-12-older.md", "# Older <script>\n\nBody & more.\n")
    _write(src, "2026-11-13-newer.md", POST)
    _write(src, "2026-11-14-secret.md", "# Secret\n\n**Status:** draft\n\nUnpublished finding.\n")

    posts = blog.build(out, blog_dir=src)

    assert [p.slug for p in posts] == ["newer", "older"]
    index = (out / "index.html").read_text()
    assert index.index("A Title With code") < index.index("Older &lt;script&gt;")
    assert "<script" not in index
    assert "Secret" not in index and not (out / "posts" / "2026-11-14-secret").exists()

    page = (out / "posts" / "2026-11-13-newer" / "index.html").read_text()
    assert 'href="../../assets/style.css"' in page
    assert "<h2" in page and "Someone &amp; Kingdon" in page
    assert (out / "assets" / "style.css").exists() and (out / ".nojekyll").exists()

    feed = ET.parse(out / "feed.xml").getroot()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert [e.find("a:title", ns).text for e in feed.findall("a:entry", ns)] == ["A Title With code", "Older <script>"]


def test_repository_posts_all_parse():
    posts = blog.load_posts(drafts=True)
    assert len(posts) >= 6
    assert all(p.title and p.summary for p in posts)
