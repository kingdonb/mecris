"""tests/test_chrome_bookmarks.py — Unit tests for Chrome Bookmarks parser.

Covers: flatten_bookmarks, filter_by_keyword, get_bookmarks_by_topic,
        load_bookmarks, and _webkit_to_datetime.
Toward kingdonb/mecris#201 / yebyen/mecris#279.
"""

import json
import os
import tempfile

import pytest

from tools.chrome_bookmarks import (
    _webkit_to_datetime,
    filter_by_keyword,
    flatten_bookmarks,
    get_bookmarks_by_topic,
    load_bookmarks,
)

# ---------------------------------------------------------------------------
# Shared test fixture — a minimal but representative bookmarks JSON structure
# ---------------------------------------------------------------------------

SAMPLE_RAW = {
    "roots": {
        "bookmark_bar": {
            "type": "folder",
            "name": "Bookmarks bar",
            "children": [
                {
                    "type": "url",
                    "name": "Python Docs",
                    "url": "https://docs.python.org",
                    "date_added": "13346400000000000",
                },
                {
                    "type": "folder",
                    "name": "Work",
                    "children": [
                        {
                            "type": "url",
                            "name": "GitHub",
                            "url": "https://github.com",
                            "date_added": "13346400000000001",
                        },
                        {
                            "type": "url",
                            "name": "Jira Board",
                            "url": "https://company.atlassian.net/jira",
                            "date_added": "13346400000000002",
                        },
                    ],
                },
            ],
        },
        "other": {
            "type": "folder",
            "name": "Other bookmarks",
            "children": [
                {
                    "type": "url",
                    "name": "Mecris Repo",
                    "url": "https://github.com/kingdonb/mecris",
                    "date_added": "13346400000000003",
                }
            ],
        },
        "synced": {
            "type": "folder",
            "name": "Mobile bookmarks",
            "children": [],
        },
    }
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_tmp_bookmarks(data: dict) -> str:
    """Write *data* to a temp file and return the path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(data, fh)
        return fh.name


# ---------------------------------------------------------------------------
# Tests: flatten_bookmarks
# ---------------------------------------------------------------------------


def test_flatten_returns_list():
    result = flatten_bookmarks(SAMPLE_RAW)
    assert isinstance(result, list)


def test_flatten_correct_count():
    result = flatten_bookmarks(SAMPLE_RAW)
    # Python Docs, GitHub, Jira Board, Mecris Repo
    assert len(result) == 4


def test_flatten_url_fields_present():
    result = flatten_bookmarks(SAMPLE_RAW)
    for item in result:
        assert "title" in item
        assert "url" in item
        assert "date_added" in item
        assert "folder" in item


def test_flatten_folder_path_nested():
    result = flatten_bookmarks(SAMPLE_RAW)
    by_title = {b["title"]: b for b in result}
    # Full path includes the root folder name ("Bookmarks bar") as prefix
    assert by_title["GitHub"]["folder"] == "Bookmarks bar/Work"
    assert by_title["Jira Board"]["folder"] == "Bookmarks bar/Work"


def test_flatten_top_level_has_root_folder():
    result = flatten_bookmarks(SAMPLE_RAW)
    by_title = {b["title"]: b for b in result}
    # Top-level bookmarks under bookmark_bar are in the "Bookmarks bar" folder
    assert by_title["Python Docs"]["folder"] == "Bookmarks bar"


def test_flatten_empty_raw():
    assert flatten_bookmarks({}) == []


def test_flatten_missing_roots():
    assert flatten_bookmarks({"roots": {}}) == []


def test_flatten_date_added_is_iso_string():
    result = flatten_bookmarks(SAMPLE_RAW)
    # Every date_added should be a non-None ISO string for our sample timestamps
    for item in result:
        assert item["date_added"] is not None
        # Must be parseable as ISO 8601
        from datetime import datetime
        datetime.fromisoformat(item["date_added"].replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Tests: filter_by_keyword
# ---------------------------------------------------------------------------


def test_filter_matches_title():
    bookmarks = flatten_bookmarks(SAMPLE_RAW)
    result = filter_by_keyword(bookmarks, "python")
    assert len(result) == 1
    assert result[0]["title"] == "Python Docs"


def test_filter_matches_url():
    bookmarks = flatten_bookmarks(SAMPLE_RAW)
    result = filter_by_keyword(bookmarks, "atlassian")
    assert len(result) == 1
    assert result[0]["title"] == "Jira Board"


def test_filter_matches_folder():
    bookmarks = flatten_bookmarks(SAMPLE_RAW)
    result = filter_by_keyword(bookmarks, "work")
    # GitHub and Jira Board are both in the "Work" folder
    assert len(result) == 2


def test_filter_case_insensitive():
    bookmarks = flatten_bookmarks(SAMPLE_RAW)
    lower = filter_by_keyword(bookmarks, "github")
    upper = filter_by_keyword(bookmarks, "GITHUB")
    mixed = filter_by_keyword(bookmarks, "GitHub")
    assert len(lower) == len(upper) == len(mixed)
    assert len(lower) >= 1


def test_filter_empty_keyword_returns_all():
    bookmarks = flatten_bookmarks(SAMPLE_RAW)
    result = filter_by_keyword(bookmarks, "")
    assert result == bookmarks


def test_filter_no_match_returns_empty():
    bookmarks = flatten_bookmarks(SAMPLE_RAW)
    result = filter_by_keyword(bookmarks, "zzznomatchxyz")
    assert result == []


# ---------------------------------------------------------------------------
# Tests: load_bookmarks
# ---------------------------------------------------------------------------


def test_load_bookmarks_from_file():
    tmppath = _write_tmp_bookmarks(SAMPLE_RAW)
    try:
        result = load_bookmarks(tmppath)
        assert "roots" in result
    finally:
        os.unlink(tmppath)


def test_load_bookmarks_file_not_found():
    result = load_bookmarks("/nonexistent/path/to/Bookmarks")
    assert result == {}


def test_load_bookmarks_invalid_json():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("not valid json {{{{")
        tmppath = fh.name
    try:
        result = load_bookmarks(tmppath)
        assert result == {}
    finally:
        os.unlink(tmppath)


# ---------------------------------------------------------------------------
# Tests: get_bookmarks_by_topic
# ---------------------------------------------------------------------------


def test_get_bookmarks_by_topic_with_match():
    tmppath = _write_tmp_bookmarks(SAMPLE_RAW)
    try:
        result = get_bookmarks_by_topic("python", path=tmppath)
        assert result["keyword"] == "python"
        assert result["match_count"] == 1
        assert result["total_bookmarks"] == 4
        assert result["matches"][0]["title"] == "Python Docs"
        assert result["source"] == tmppath
    finally:
        os.unlink(tmppath)


def test_get_bookmarks_by_topic_no_file():
    result = get_bookmarks_by_topic("python", path="/nonexistent/Bookmarks")
    assert result["keyword"] == "python"
    assert result["match_count"] == 0
    assert result["total_bookmarks"] == 0
    assert result["source"] == "not found"


def test_get_bookmarks_by_topic_empty_keyword():
    tmppath = _write_tmp_bookmarks(SAMPLE_RAW)
    try:
        result = get_bookmarks_by_topic("", path=tmppath)
        assert result["match_count"] == result["total_bookmarks"]
    finally:
        os.unlink(tmppath)


# ---------------------------------------------------------------------------
# Tests: _webkit_to_datetime
# ---------------------------------------------------------------------------


def test_webkit_to_datetime_recent_timestamp():
    # 13346400000000000 µs from 1601-01-01 should land in a recent year
    dt = _webkit_to_datetime(13346400000000000)
    assert dt is not None
    assert dt.year >= 2020


def test_webkit_to_datetime_returns_utc():
    from datetime import timezone

    dt = _webkit_to_datetime(13346400000000000)
    assert dt is not None
    assert dt.tzinfo == timezone.utc


def test_webkit_to_datetime_large_value():
    # Sanity check: a huge value should still parse without raising
    dt = _webkit_to_datetime(13999999999999999)
    # May be None if out of platform range, but must not raise
    assert dt is None or hasattr(dt, "year")
