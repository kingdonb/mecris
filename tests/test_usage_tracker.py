import pytest
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from usage_tracker import UsageTracker

from unittest.mock import patch

@pytest.fixture
def tracker():
    with patch("usage_tracker.UsageTracker.init_database"):
        return UsageTracker()

def test_calculate_cost_sonnet(tracker):
    # Sonnet pricing: input $3/million, output $15/million
    # 1,000,000 input tokens, 2,000,000 output tokens => cost = 3*1 + 15*2 = $33
    cost = tracker.calculate_cost("claude-3-5-sonnet-20241022", 1_000_000, 2_000_000)
    assert cost == 33.0

def test_calculate_cost_haiku_default(tracker):
    # Unknown model falls back to Sonnet pricing
    cost = tracker.calculate_cost("unknown-model", 500_000, 500_000)
    # Expected: input 0.5M * $3 = $1.5, output 0.5M * $15 = $7.5, total $9.0
    assert cost == 9.0

def test_autonomous_tables_exist():
    """Verify the new autonomous tables are present and accessible."""
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        pytest.skip("NEON_DB_URL not set")
        
    import psycopg2
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor() as cur:
            # Check autonomous_turns
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'autonomous_turns'")
            columns = [row[0] for row in cur.fetchall()]
            assert "agent_type" in columns
            assert "agenda_slug" in columns
            
            # Check token_bank
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'token_bank'")
            columns = [row[0] for row in cur.fetchall()]
            assert "available_tokens" in columns
            assert "monthly_limit" in columns
