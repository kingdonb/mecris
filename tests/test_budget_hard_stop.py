import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from virtual_budget_manager import VirtualBudgetManager, Provider

@pytest.fixture
def mock_psycopg2():
    with patch("virtual_budget_manager.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        
        # Connection context manager
        mock_connect.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn
        
        # Cursor behavior: return our mock_cur regardless of factory args
        mock_conn.cursor.return_value = mock_cur
        mock_cur.__enter__.return_value = mock_cur
        
        yield mock_cur

@pytest.mark.asyncio
async def test_budget_status_exhausted_alert(mock_psycopg2):
    """Test that it returns BUDGET_EXHAUSTED alert and is_halted when budget is <= 0."""
    # We must patch _ensure_daily_budget to avoid it consuming fetchone() calls
    with patch("virtual_budget_manager.VirtualBudgetManager._ensure_daily_budget"):
        vbm = VirtualBudgetManager()
        
        # Mock finding a daily budget with 0 remaining
        # Result must support dictionary access for RealDictCursor
        mock_data = {
            "budget_amount": 2.0, 
            "remaining_amount": -0.01, 
            "updated_at": datetime.now()
        }
        mock_psycopg2.fetchone.return_value = mock_data
        
        # Provider usage and reconciliation queries return empty lists
        mock_psycopg2.fetchall.return_value = [] 
        
        status = vbm.get_budget_status()
        
        assert "BUDGET_EXHAUSTED" in status["alerts"]
        assert status["budget_health"] == "CRITICAL"
        assert status["is_halted"] is True

@pytest.mark.asyncio
async def test_record_usage_fails_when_exhausted(mock_psycopg2):
    """Test that record_usage returns recorded: False when budget is already exhausted."""
    with patch("virtual_budget_manager.VirtualBudgetManager._ensure_daily_budget"):
        vbm = VirtualBudgetManager()
        
        # can_afford check: uses a standard cursor (index access) or dict
        # In our code: rem = res[0]
        mock_psycopg2.fetchone.return_value = [0.0] 
        
        result = vbm.record_usage(Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 1000, 1000)
        
        assert result["recorded"] is False
        assert result["reason"] == "BUDGET_EXHAUSTED"
