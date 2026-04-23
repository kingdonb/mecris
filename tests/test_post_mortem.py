"""Tests for PostMortemGenerator — Plan: yebyen/mecris#255 / kingdonb/mecris#216"""
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from ghost.post_mortem import PostMortemGenerator

USER_ID = "test-user-sub-123"
FAKE_DB_URL = "postgres://fake"
TS = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)

FAILED_TURN = {
    "turn_id": 42,
    "agent_role": "Archivist",
    "start_time": TS,
    "end_time": TS,
    "exit_code": 1,
    "tokens_consumed": 300,
    "summary": "Timeout during archive: connection refused",
}


@pytest.fixture
def tmp_output(tmp_path):
    return tmp_path / "post-mortems"


@pytest.fixture
def generator(tmp_output):
    return PostMortemGenerator(db_url=FAKE_DB_URL, output_dir=tmp_output)


# ---------------------------------------------------------------------------
# No failures — nothing generated
# ---------------------------------------------------------------------------

def test_no_failures_returns_none(generator):
    """When no failed turns exist, run() returns None."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[]):
        result = generator.run(USER_ID)
    assert result is None


def test_no_failures_creates_no_files(generator, tmp_output):
    """When no failed turns exist, no file is written."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[]):
        generator.run(USER_ID)
    assert not tmp_output.exists() or list(tmp_output.iterdir()) == []


# ---------------------------------------------------------------------------
# One failed turn — file drafted correctly
# ---------------------------------------------------------------------------

def test_one_failure_returns_path(generator, tmp_output):
    """A single failed turn produces a file path that exists on disk."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = generator.run(USER_ID)
    assert path is not None
    assert path.exists()


def test_one_failure_filename_contains_date(generator, tmp_output):
    """The generated filename includes the ISO date of the failed turn."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = generator.run(USER_ID)
    assert "2026-04-22" in path.name


def test_one_failure_filename_contains_turn_id(generator, tmp_output):
    """The generated filename includes the turn_id."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = generator.run(USER_ID)
    assert "turn42" in path.name


def test_one_failure_content_has_required_sections(generator, tmp_output):
    """The post-mortem file must contain all three required sections."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = generator.run(USER_ID)
    content = path.read_text()
    assert "## Summary" in content
    assert "## Captured Output" in content
    assert "## Proposed Fix" in content


def test_one_failure_content_includes_metadata(generator, tmp_output):
    """The report includes agent_role, turn_id, and summary text."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = generator.run(USER_ID)
    content = path.read_text()
    assert "Archivist" in content
    assert "42" in content
    assert "Timeout during archive" in content


def test_one_failure_exit_code_formatted(generator, tmp_output):
    """The exit code is rendered in backtick format for markdown clarity."""
    with patch.object(generator.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = generator.run(USER_ID)
    content = path.read_text()
    assert "`1`" in content


def test_one_failure_output_dir_created(tmp_path):
    """The output directory is created if it does not exist yet."""
    nonexistent = tmp_path / "deep" / "nested" / "post-mortems"
    gen = PostMortemGenerator(db_url=FAKE_DB_URL, output_dir=nonexistent)
    with patch.object(gen.bank, "get_failed_turns", return_value=[FAILED_TURN]):
        path = gen.run(USER_ID)
    assert nonexistent.exists()
    assert path.exists()


# ---------------------------------------------------------------------------
# Multiple failed turns — most recent (first) used, only one file generated
# ---------------------------------------------------------------------------

def test_multiple_failures_uses_most_recent(generator, tmp_output):
    """When multiple failures exist, the most-recent (index 0) is reported."""
    older = {**FAILED_TURN, "turn_id": 10, "start_time": datetime(2026, 4, 1, tzinfo=timezone.utc), "summary": "Older failure"}
    newer = {**FAILED_TURN, "turn_id": 99, "start_time": datetime(2026, 4, 22, tzinfo=timezone.utc), "summary": "Newer failure"}
    # get_failed_turns returns most-recent first (ORDER BY start_time DESC)
    with patch.object(generator.bank, "get_failed_turns", return_value=[newer, older]):
        path = generator.run(USER_ID)
    content = path.read_text()
    assert "Newer failure" in content
    assert "99" in content


def test_multiple_failures_only_one_file_generated(generator, tmp_output):
    """Only one post-mortem file is created per run() call."""
    older = {**FAILED_TURN, "turn_id": 10, "summary": "Old"}
    newer = {**FAILED_TURN, "turn_id": 99, "summary": "New"}
    with patch.object(generator.bank, "get_failed_turns", return_value=[newer, older]):
        generator.run(USER_ID)
    files = list(tmp_output.iterdir())
    assert len(files) == 1


# ---------------------------------------------------------------------------
# No DB — fail-open (no crash, no file)
# ---------------------------------------------------------------------------

def test_no_db_url_returns_none(tmp_output):
    """Without NEON_DB_URL, run() returns None gracefully (fail-open)."""
    with patch.dict("os.environ", {}, clear=True):
        gen = PostMortemGenerator(db_url=None, output_dir=tmp_output)
        result = gen.run(USER_ID)
    assert result is None


def test_no_db_url_no_file_created(tmp_output):
    """Without NEON_DB_URL, no file is written."""
    with patch.dict("os.environ", {}, clear=True):
        gen = PostMortemGenerator(db_url=None, output_dir=tmp_output)
        gen.run(USER_ID)
    assert not tmp_output.exists() or list(tmp_output.iterdir()) == []
