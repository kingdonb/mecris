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
