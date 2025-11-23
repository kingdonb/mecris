import pytest
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from usage_tracker import UsageTracker

@pytest.fixture
def tracker():
    # Use in-memory db to avoid side effects
    return UsageTracker(db_path=":memory:")

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
