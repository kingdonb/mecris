"""
Unit tests for scripts/chunk_session_logs.py

Covers: parse_log, extract_primary_activity, write_chunk, write_preamble, main.
All tests are pure-logic / in-memory; no network or DB calls needed.
"""
import sys
import types
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Bootstrap: chunk_session_logs only needs stdlib — safe to import directly.
from scripts.chunk_session_logs import (
    DATE_HEADER_RE,
    extract_primary_activity,
    main,
    parse_log,
    write_chunk,
    write_preamble,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SINGLE_ENTRY = """\
## 2026-04-01 — Session 1: First session
Body line 1
Body line 2
"""

MULTI_DATE = """\
## 2026-04-01 — Session 1: Alpha
Alpha body

## 2026-04-02 — Session 2: Beta
Beta body
"""

SAME_DAY_TWO = """\
## 2026-04-01 — Morning session
Morning body

## 2026-04-01 — Evening session
Evening body
"""

WITH_PREAMBLE = """\
# session_log.md
Preamble text here.

## 2026-04-10 — Post-preamble session
Entry body
"""

EMOJI_HEADER = """\
## 🏛️ 2026-04-05 — Emoji session
Emoji body
"""

H3_HEADER = """\
### 2026-05-01 — Deep section
Deep body
"""

# ---------------------------------------------------------------------------
# DATE_HEADER_RE sanity checks
# ---------------------------------------------------------------------------

class TestDateHeaderRe:
    def test_standard_em_dash(self):
        m = DATE_HEADER_RE.match("## 2026-04-01 — Session 1: Alpha")
        assert m is not None
        assert m.group(2) == "2026-04-01"
        assert "Alpha" in m.group(3)

    def test_emoji_prefix(self):
        m = DATE_HEADER_RE.match("## 🏛️ 2026-04-05 — Emoji session")
        assert m is not None
        assert m.group(2) == "2026-04-05"

    def test_h3_level(self):
        m = DATE_HEADER_RE.match("### 2026-05-01 — Deep section")
        assert m is not None
        assert m.group(1) == "###"

    def test_no_match_plain_heading(self):
        assert DATE_HEADER_RE.match("## Not a dated section") is None

    def test_no_match_empty(self):
        assert DATE_HEADER_RE.match("") is None


# ---------------------------------------------------------------------------
# parse_log
# ---------------------------------------------------------------------------

class TestParseLog:
    def test_empty_string_returns_empty(self):
        preamble, sections = parse_log("")
        assert preamble == ""
        assert sections == {}

    def test_no_headers_all_preamble(self):
        text = "Just some text\nwith no date headers\n"
        preamble, sections = parse_log(text)
        assert "Just some text" in preamble
        assert sections == {}

    def test_single_entry_one_date_key(self):
        preamble, sections = parse_log(SINGLE_ENTRY)
        assert preamble == ""
        assert "2026-04-01" in sections
        assert len(sections["2026-04-01"]) == 1

    def test_single_entry_title_captured(self):
        _, sections = parse_log(SINGLE_ENTRY)
        level, title, body = sections["2026-04-01"][0]
        assert title == "Session 1: First session"

    def test_single_entry_body_captured(self):
        _, sections = parse_log(SINGLE_ENTRY)
        _, _, body = sections["2026-04-01"][0]
        assert "Body line 1" in body
        assert "Body line 2" in body

    def test_multi_date_two_keys(self):
        _, sections = parse_log(MULTI_DATE)
        assert set(sections.keys()) == {"2026-04-01", "2026-04-02"}

    def test_same_day_two_entries(self):
        _, sections = parse_log(SAME_DAY_TWO)
        assert len(sections["2026-04-01"]) == 2

    def test_same_day_titles_in_order(self):
        _, sections = parse_log(SAME_DAY_TWO)
        titles = [e[1] for e in sections["2026-04-01"]]
        assert titles == ["Morning session", "Evening session"]

    def test_preamble_before_first_header(self):
        preamble, sections = parse_log(WITH_PREAMBLE)
        assert "Preamble text here" in preamble
        assert "2026-04-10" in sections

    def test_preamble_not_in_sections(self):
        preamble, _ = parse_log(WITH_PREAMBLE)
        assert "# session_log.md" in preamble

    def test_emoji_prefix_date_parsed(self):
        _, sections = parse_log(EMOJI_HEADER)
        assert "2026-04-05" in sections

    def test_h3_level_preserved(self):
        _, sections = parse_log(H3_HEADER)
        level, _, _ = sections["2026-05-01"][0]
        assert level == "###"


# ---------------------------------------------------------------------------
# extract_primary_activity
# ---------------------------------------------------------------------------

class TestExtractPrimaryActivity:
    def test_empty_list_returns_unknown(self):
        assert extract_primary_activity([]) == "unknown"

    def test_single_entry_returns_title(self):
        entries = [("##", "My Title", "body")]
        assert extract_primary_activity(entries) == "My Title"

    def test_multiple_entries_returns_first_title(self):
        entries = [("##", "First", "b1"), ("##", "Second", "b2")]
        assert extract_primary_activity(entries) == "First"


# ---------------------------------------------------------------------------
# write_chunk
# ---------------------------------------------------------------------------

class TestWriteChunk:
    def test_dry_run_returns_path_without_writing(self, tmp_path):
        entries = [("##", "Test session", "Some body")]
        out = write_chunk(tmp_path, "2026-04-01", entries, dry_run=True)
        assert out == tmp_path / "2026-04-01.md"
        assert not out.exists()

    def test_writes_file_when_not_dry_run(self, tmp_path):
        entries = [("##", "Test session", "Some body")]
        out = write_chunk(tmp_path, "2026-04-01", entries, dry_run=False)
        assert out.exists()

    def test_output_path_is_date_dot_md(self, tmp_path):
        entries = [("##", "Title", "body")]
        out = write_chunk(tmp_path, "2026-05-15", entries, dry_run=True)
        assert out.name == "2026-05-15.md"

    def test_front_matter_contains_date(self, tmp_path):
        entries = [("##", "Title", "body")]
        out = write_chunk(tmp_path, "2026-04-01", entries, dry_run=False)
        content = out.read_text()
        assert "date: 2026-04-01" in content

    def test_front_matter_contains_primary_activity(self, tmp_path):
        entries = [("##", "My Activity", "body")]
        out = write_chunk(tmp_path, "2026-04-01", entries, dry_run=False)
        content = out.read_text()
        assert 'primary_activity: "My Activity"' in content

    def test_front_matter_entry_count(self, tmp_path):
        entries = [("##", "A", "b1"), ("##", "B", "b2")]
        out = write_chunk(tmp_path, "2026-04-01", entries, dry_run=False)
        content = out.read_text()
        assert "entry_count: 2" in content

    def test_body_content_present(self, tmp_path):
        entries = [("##", "Title", "## 2026-04-01 — Title\nsome content")]
        out = write_chunk(tmp_path, "2026-04-01", entries, dry_run=False)
        content = out.read_text()
        assert "some content" in content

    def test_creates_output_dir_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b"
        entries = [("##", "T", "body")]
        write_chunk(nested, "2026-04-01", entries, dry_run=False)
        assert nested.exists()


# ---------------------------------------------------------------------------
# write_preamble
# ---------------------------------------------------------------------------

class TestWritePreamble:
    def test_empty_preamble_returns_none(self, tmp_path):
        assert write_preamble(tmp_path, "", dry_run=True) is None

    def test_whitespace_only_returns_none(self, tmp_path):
        assert write_preamble(tmp_path, "   \n\n  ", dry_run=True) is None

    def test_dry_run_returns_path_without_writing(self, tmp_path):
        out = write_preamble(tmp_path, "Some preamble", dry_run=True)
        assert out == tmp_path / "PREAMBLE.md"
        assert not out.exists()

    def test_writes_preamble_file(self, tmp_path):
        out = write_preamble(tmp_path, "Some preamble content", dry_run=False)
        assert out.exists()
        assert out.name == "PREAMBLE.md"

    def test_preamble_content_in_file(self, tmp_path):
        out = write_preamble(tmp_path, "Preamble content here", dry_run=False)
        content = out.read_text()
        assert "Preamble content here" in content

    def test_preamble_has_front_matter(self, tmp_path):
        out = write_preamble(tmp_path, "Some preamble", dry_run=False)
        content = out.read_text()
        assert "date: preamble" in content


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    def test_missing_input_file_returns_1(self, tmp_path):
        rc = main(["--input", str(tmp_path / "nonexistent.md")])
        assert rc == 1

    def test_dry_run_returns_0(self, tmp_path):
        log_file = tmp_path / "session_log.md"
        log_file.write_text(MULTI_DATE, encoding="utf-8")
        rc = main(["--input", str(log_file), "--dry-run"])
        assert rc == 0

    def test_dry_run_writes_no_files(self, tmp_path):
        log_file = tmp_path / "session_log.md"
        log_file.write_text(MULTI_DATE, encoding="utf-8")
        out_dir = tmp_path / "chunks"
        main(["--input", str(log_file), "--output-dir", str(out_dir), "--dry-run"])
        assert not out_dir.exists()

    def test_normal_run_writes_chunk_files(self, tmp_path):
        log_file = tmp_path / "session_log.md"
        log_file.write_text(MULTI_DATE, encoding="utf-8")
        out_dir = tmp_path / "chunks"
        rc = main(["--input", str(log_file), "--output-dir", str(out_dir)])
        assert rc == 0
        assert (out_dir / "2026-04-01.md").exists()
        assert (out_dir / "2026-04-02.md").exists()

    def test_normal_run_writes_preamble_when_present(self, tmp_path):
        log_file = tmp_path / "session_log.md"
        log_file.write_text(WITH_PREAMBLE, encoding="utf-8")
        out_dir = tmp_path / "chunks"
        main(["--input", str(log_file), "--output-dir", str(out_dir)])
        assert (out_dir / "PREAMBLE.md").exists()

    def test_no_preamble_file_when_no_preamble(self, tmp_path):
        log_file = tmp_path / "session_log.md"
        log_file.write_text(SINGLE_ENTRY, encoding="utf-8")
        out_dir = tmp_path / "chunks"
        main(["--input", str(log_file), "--output-dir", str(out_dir)])
        assert not (out_dir / "PREAMBLE.md").exists()

    def test_empty_log_returns_0(self, tmp_path):
        log_file = tmp_path / "session_log.md"
        log_file.write_text("", encoding="utf-8")
        rc = main(["--input", str(log_file)])
        assert rc == 0
