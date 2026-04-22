"""Tests for TokenBankService — Plan: yebyen/mecris#254 / kingdonb/mecris#209"""
import pytest
from unittest.mock import patch, MagicMock, call
from services.token_bank import TokenBankService, TokenBudgetExceededError

FAKE_DB_URL = "postgres://fake"
USER_ID = "test-user-sub-123"
AGENT_ROLE = "Archivist"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_psycopg2():
    """Patch psycopg2 in the token_bank module; yield the cursor mock."""
    with patch("services.token_bank.psycopg2") as mock_pg:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pg.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pg.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_cur, mock_conn


@pytest.fixture
def bank():
    return TokenBankService(db_url=FAKE_DB_URL)


# ---------------------------------------------------------------------------
# No DB URL — fail-open behaviour
# ---------------------------------------------------------------------------

def test_no_db_url_allows_turn():
    """Without NEON_DB_URL, check_and_debit returns 0 (fail-open)."""
    svc = TokenBankService(db_url=None)
    with patch.dict("os.environ", {}, clear=True):
        result = svc.check_and_debit(USER_ID, 1000, AGENT_ROLE)
    assert result == 0


def test_no_db_url_record_turn_start_returns_none():
    svc = TokenBankService(db_url=None)
    assert svc.record_turn_start(USER_ID, AGENT_ROLE) is None


def test_no_db_url_record_turn_end_is_noop():
    svc = TokenBankService(db_url=None)
    svc.record_turn_end(42, exit_code=0, tokens_consumed=100)  # must not raise


def test_no_db_url_get_failed_turns_returns_empty():
    svc = TokenBankService(db_url=None)
    assert svc.get_failed_turns(USER_ID) == []


# ---------------------------------------------------------------------------
# check_and_debit — success path
# ---------------------------------------------------------------------------

def test_check_and_debit_allows_when_under_limit(bank, mock_psycopg2):
    """When tokens_used_today + requested <= daily_allowance, debit succeeds."""
    mock_cur, mock_conn = mock_psycopg2
    # _ensure_row and _reset_if_new_day only call execute(), not fetchone().
    # Simulate: allowance=50000, used=10000 → 40000 remaining; request 5000
    mock_cur.fetchone.side_effect = [
        (50000, 10000), # SELECT daily_allowance, tokens_used_today FOR UPDATE
        (15000,),       # UPDATE RETURNING tokens_used_today
    ]

    result = bank.check_and_debit(USER_ID, 5000, AGENT_ROLE)
    assert result == 15000


# ---------------------------------------------------------------------------
# check_and_debit — rejection path
# ---------------------------------------------------------------------------

def test_check_and_debit_raises_when_exceeded(bank, mock_psycopg2):
    """When tokens_used_today + requested > daily_allowance, raise TokenBudgetExceededError."""
    mock_cur, mock_conn = mock_psycopg2
    # Simulate: allowance=50000, used=49000 → only 1000 remaining; request 2000
    mock_cur.fetchone.side_effect = [
        (50000, 49000), # SELECT FOR UPDATE
    ]

    with pytest.raises(TokenBudgetExceededError) as exc_info:
        bank.check_and_debit(USER_ID, 2000, AGENT_ROLE)

    assert "49000/50000" in str(exc_info.value)
    assert "Archivist" in str(exc_info.value)


def test_check_and_debit_raises_when_exactly_full(bank, mock_psycopg2):
    """Edge: used == allowance → no room at all, even for 1 token."""
    mock_cur, mock_conn = mock_psycopg2
    mock_cur.fetchone.side_effect = [
        (50000, 50000),  # completely full
    ]

    with pytest.raises(TokenBudgetExceededError):
        bank.check_and_debit(USER_ID, 1, AGENT_ROLE)


def test_check_and_debit_allows_exact_remaining(bank, mock_psycopg2):
    """Edge: requesting exactly the remaining allowance should succeed."""
    mock_cur, mock_conn = mock_psycopg2
    mock_cur.fetchone.side_effect = [
        (50000, 45000),  # 5000 remaining
        (50000,),        # after debit
    ]

    result = bank.check_and_debit(USER_ID, 5000, AGENT_ROLE)
    assert result == 50000


# ---------------------------------------------------------------------------
# record_turn_start / record_turn_end
# ---------------------------------------------------------------------------

def test_record_turn_start_returns_turn_id(bank, mock_psycopg2):
    mock_cur, mock_conn = mock_psycopg2
    mock_cur.fetchone.return_value = (42,)

    turn_id = bank.record_turn_start(USER_ID, AGENT_ROLE)
    assert turn_id == 42


def test_record_turn_end_updates_row(bank, mock_psycopg2):
    mock_cur, mock_conn = mock_psycopg2

    bank.record_turn_end(42, exit_code=0, tokens_consumed=1234, summary="All good")

    # Verify UPDATE was called with the right positional args
    args, _ = mock_cur.execute.call_args
    query, params = args[0], args[1]
    assert "UPDATE autonomous_turns" in query
    assert params == (0, 1234, "All good", 42)


def test_record_turn_end_failure_exit_code(bank, mock_psycopg2):
    """Non-zero exit_code should be persisted correctly."""
    mock_cur, mock_conn = mock_psycopg2

    bank.record_turn_end(99, exit_code=1, tokens_consumed=500, summary="Crashed")

    args, _ = mock_cur.execute.call_args
    params = args[1]
    assert params[0] == 1   # exit_code
    assert params[1] == 500
    assert params[2] == "Crashed"


# ---------------------------------------------------------------------------
# get_failed_turns
# ---------------------------------------------------------------------------

def test_get_failed_turns_returns_structured_list(bank, mock_psycopg2):
    from datetime import datetime, timezone
    mock_cur, mock_conn = mock_psycopg2
    ts = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    mock_cur.fetchall.return_value = [
        (7, "Archivist", ts, ts, 1, 300, "Timeout during archive"),
    ]

    result = bank.get_failed_turns(USER_ID, limit=5)

    assert len(result) == 1
    assert result[0]["turn_id"] == 7
    assert result[0]["exit_code"] == 1
    assert result[0]["agent_role"] == "Archivist"
    assert result[0]["summary"] == "Timeout during archive"


def test_get_failed_turns_empty(bank, mock_psycopg2):
    mock_cur, mock_conn = mock_psycopg2
    mock_cur.fetchall.return_value = []

    result = bank.get_failed_turns(USER_ID)
    assert result == []
