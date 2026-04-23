"""
Tests for scripts/add_docs_frontmatter.py — RAG Foundation (kingdonb/mecris#202)
"""

import sys
import textwrap
from pathlib import Path

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from add_docs_frontmatter import (
    _extract_description,
    _extract_tags,
    _extract_title,
    build_frontmatter,
    process_file,
)


# ── _extract_title ─────────────────────────────────────────────────────────────

def test_extract_title_h1():
    text = "# My Great Document\n\nSome text here."
    assert _extract_title(text, 'MY_GREAT_DOCUMENT') == 'My Great Document'


def test_extract_title_h1_strips_formatting():
    text = "# **Bold Title** with `code`\n\nSome text."
    result = _extract_title(text, 'stem')
    assert 'Bold Title' in result
    assert '**' not in result
    assert '`' not in result


def test_extract_title_fallback_to_stem():
    text = "No heading here, just prose."
    result = _extract_title(text, 'AGENT_OPS_RUNBOOK')
    assert result == 'Agent Ops Runbook'


def test_extract_title_stem_with_dashes():
    text = "Just prose."
    result = _extract_title(text, 'mcp-groq-debugging')
    assert result == 'Mcp Groq Debugging'


# ── _extract_description ───────────────────────────────────────────────────────

def test_extract_description_basic():
    text = "# Title\n\nThis is a useful description sentence for the document.\n"
    result = _extract_description(text)
    assert 'useful description' in result


def test_extract_description_skips_heading():
    text = "# Title\n\n## Subtitle\n\nReal content starts here with enough chars.\n"
    result = _extract_description(text)
    assert 'Real content' in result


def test_extract_description_fallback():
    text = "# Title\n\n---\n\n```code block```\n"
    result = _extract_description(text)
    assert result == 'Mecris project documentation.'


def test_extract_description_strips_markdown():
    text = "# Title\n\nThis has **bold** and [a link](http://example.com) inside.\n"
    result = _extract_description(text)
    assert '**' not in result
    assert '[' not in result


# ── _extract_tags ──────────────────────────────────────────────────────────────

def test_extract_tags_underscore_stem():
    tags = _extract_tags('ANDROID_APP_DESIGN')
    assert 'android' in tags
    assert 'app' in tags
    assert 'design' in tags


def test_extract_tags_dash_stem():
    tags = _extract_tags('mcp-groq-debugging')
    assert 'mcp' in tags
    assert 'groq' in tags
    assert 'debugging' in tags


def test_extract_tags_deduplication():
    tags = _extract_tags('FOO_FOO_BAR')
    assert tags.count('foo') == 1


def test_extract_tags_filters_stop_words():
    tags = _extract_tags('THE_AND_OR_GUIDE')
    assert 'the' not in tags
    assert 'and' not in tags
    assert 'or' not in tags
    assert 'guide' in tags


def test_extract_tags_filters_short_words():
    tags = _extract_tags('A2P_IT_GUIDE')
    # 'it' is 2 chars, should be filtered (len > 2 required)
    assert 'it' not in tags


# ── build_frontmatter ──────────────────────────────────────────────────────────

def test_build_frontmatter_structure():
    fm = build_frontmatter('Test Title', 'A description.', ['tag1', 'tag2'], '2026-01-01')
    assert fm.startswith('---\n')
    assert 'title: "Test Title"' in fm
    assert 'description: "A description."' in fm
    assert '"tag1"' in fm
    assert '"tag2"' in fm
    assert 'date: "2026-01-01"' in fm
    assert fm.endswith('---\n\n')


def test_build_frontmatter_escapes_quotes():
    fm = build_frontmatter('Title with "quotes"', 'Desc.', [], '2026-01-01')
    assert '"quotes"' not in fm or fm.count('"') % 2 == 0  # no unbalanced quotes


# ── process_file (integration) ─────────────────────────────────────────────────

def test_process_file_adds_frontmatter(tmp_path):
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    f = docs_dir / 'TEST_DOC.md'
    f.write_text('# Test Document\n\nThis is a sufficient description paragraph here.\n')

    result = process_file(f, docs_dir, dry_run=False, force=False)
    assert result == 'updated'

    content = f.read_text()
    assert content.startswith('---\n')
    assert 'title: "Test Document"' in content


def test_process_file_skips_existing_frontmatter(tmp_path):
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    f = docs_dir / 'ALREADY.md'
    f.write_text('---\ntitle: "Existing"\n---\n\nContent here.\n')

    result = process_file(f, docs_dir, dry_run=False, force=False)
    assert result == 'skipped'


def test_process_file_force_overwrites(tmp_path):
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    f = docs_dir / 'REPLACE.md'
    f.write_text('---\ntitle: "Old Title"\n---\n\nContent here now.\n')

    result = process_file(f, docs_dir, dry_run=False, force=True)
    assert result == 'updated'
    content = f.read_text()
    assert 'Old Title' not in content


def test_process_file_dry_run_no_write(tmp_path):
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    f = docs_dir / 'DRY.md'
    original = '# Dry Run Test\n\nContent here unchanged.\n'
    f.write_text(original)

    result = process_file(f, docs_dir, dry_run=True, force=False)
    assert result == 'would_update'
    assert f.read_text() == original


def test_process_file_idempotent_after_update(tmp_path):
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    f = docs_dir / 'IDEM.md'
    f.write_text('# Idempotency Test\n\nThis paragraph is long enough for the test.\n')

    process_file(f, docs_dir, dry_run=False, force=False)
    content_after_first = f.read_text()

    result2 = process_file(f, docs_dir, dry_run=False, force=False)
    assert result2 == 'skipped'
    assert f.read_text() == content_after_first
