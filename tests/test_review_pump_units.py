import pytest
from services.review_pump import ReviewPump

def test_pump_status_returns_unit():
    pump = ReviewPump(multiplier=1.0)
    # This should fail initially as 'unit' is not supported
    status = pump.get_status(current_debt=1000, tomorrow_liability=100, daily_completions=50, unit="cards")
    assert status["unit"] == "cards"

def test_pump_status_defaults_to_points():
    pump = ReviewPump(multiplier=1.0)
    status = pump.get_status(current_debt=1000, tomorrow_liability=100, daily_completions=50)
    assert status.get("unit") == "points"

def test_arabic_heuristic_conversion():
    # Simulated Arabic goal logic from mcp_server.py
    points_today = 120
    daily_done_cards = int(points_today / 12)
    assert daily_done_cards == 10
    
    pump = ReviewPump(multiplier=2.0) # 14 days
    # 140 debt -> target = 10 cards. 
    # If we did 120 points, it should be exactly on target (turbulent)
    status = pump.get_status(current_debt=140, tomorrow_liability=0, daily_completions=daily_done_cards, unit="cards")
    assert status["current_flow_rate"] == 10
    assert status["target_flow_rate"] == 10
    assert status["status"] == "turbulent"
    assert status["unit"] == "cards"
