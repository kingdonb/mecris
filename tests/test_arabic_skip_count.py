"""
Tests for services/arabic_skip_counter.py

Verifies that count_arabic_reminders:
  - returns an int in all cases
  - returns the count from the Neon HTTP response on success
  - returns 0 on HTTP error (fail-safe)
  - queries both arabic reminder type strings
  - sends the correct HTTP request shape (Neon /sql endpoint, Basic auth)
"""

import pytest
from unittest.mock import MagicMock, patch

from services.arabic_skip_counter import count_arabic_reminders

_NEON_URL = "postgresql://myuser:mypass@ep-test-123.us-east-2.aws.neon.tech/neondb"


def _make_httpx_mock(count: int) -> MagicMock:
    """Build a minimal httpx.post mock returning `count` from the Neon /sql response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"rows": [{"count": str(count)}], "fields": []}
    return mock_response


def test_returns_int_zero_when_no_rows():
    """Returns 0 (as int) when no arabic reminders are in the window."""
    mock_resp = _make_httpx_mock(0)
    with patch("httpx.post", return_value=mock_resp):
        result = count_arabic_reminders(_NEON_URL, "user1")
    assert isinstance(result, int)
    assert result == 0


def test_returns_correct_count():
    """Returns the row count from the HTTP response as an int."""
    mock_resp = _make_httpx_mock(3)
    with patch("httpx.post", return_value=mock_resp):
        result = count_arabic_reminders(_NEON_URL, "user1")
    assert isinstance(result, int)
    assert result == 3


def test_returns_zero_on_http_error():
    """Returns 0 (fail-safe) when the HTTP request raises an exception."""
    with patch("httpx.post", side_effect=Exception("connection refused")):
        result = count_arabic_reminders(_NEON_URL, "user1")
    assert isinstance(result, int)
    assert result == 0


def test_queries_correct_reminder_types():
    """HTTP request params contain both arabic_review_reminder and arabic_review_escalation."""
    mock_resp = _make_httpx_mock(5)
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        count_arabic_reminders(_NEON_URL, "user1", hours=12)

    call_kwargs = mock_post.call_args[1]
    params = call_kwargs["json"]["params"]
    assert "arabic_review_reminder" in params
    assert "arabic_review_escalation" in params
    assert "user1" in params


def test_neon_http_request_shape():
    """HTTP request targets the correct Neon /sql endpoint with Basic auth and proper body."""
    mock_resp = _make_httpx_mock(2)
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        count_arabic_reminders(
            "postgresql://myuser:mypass@ep-test.neon.tech/neondb", "user42"
        )

    call_args = mock_post.call_args
    url = call_args[0][0]
    kwargs = call_args[1]

    assert url == "https://ep-test.neon.tech/sql"
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"].startswith("Basic ")
    assert "query" in kwargs["json"]
    assert "params" in kwargs["json"]
    assert "user42" in kwargs["json"]["params"]
