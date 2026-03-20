import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from virtual_budget_manager import VirtualBudgetManager, Provider

@pytest.fixture
def mock_psycopg2():
    with patch("virtual_budget_manager.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        yield mock_cur

@pytest.mark.asyncio
async def test_budget_status_exhausted_alert(mock_psycopg2):
    """Test that it returns BUDGET_EXHAUSTED alert and is_halted when budget is <= 0."""
    vbm = VirtualBudgetManager()
    
    # Mock finding a daily budget with 0 remaining
    # Row: (budget_amount, remaining_amount, updated_at)
    mock_psycopg2.fetchone.side_effect = [
        {"id": 1}, # _ensure_daily_budget existence check
        {"budget_amount": 2.0, "remaining_amount": -0.01, "updated_at": datetime.now()} # get_budget_status fetch
    ]
    # Provider usage query
    mock_psycopg2.fetchall.side_effect = [[], []] 
    
    status = vbm.get_budget_status()
    
    assert "BUDGET_EXHAUSTED" in status["alerts"]
    assert status["budget_health"] == "CRITICAL"
    assert status["is_halted"] is True

@pytest.mark.asyncio
async def test_record_usage_fails_when_exhausted(mock_psycopg2):
    """Test that record_usage returns recorded: False when budget is already exhausted."""
    vbm = VirtualBudgetManager()
    
    # Mock budget check: remaining_amount = 0
    # can_afford check: (remaining_amount,)
    mock_psycopg2.fetchone.side_effect = [
        {"id": 1}, # _ensure_daily_budget
        (0.0,)     # can_afford check
    ]
    
    result = vbm.record_usage(Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 1000, 1000)
    
    assert result["recorded"] is False
    assert result["reason"] == "BUDGET_EXHAUSTED"
