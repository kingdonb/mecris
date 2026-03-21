import pytest
from services.review_pump import ReviewPump

def test_maintenance_lever_only_clears_liabilities():
    pump = ReviewPump(multiplier=1.0)
    # 2608 debt, 100 tomorrow liability
    target = pump.calculate_target(current_debt=2608, tomorrow_liability=100)
    assert target == 100

def test_aggressive_lever_clears_portion_of_backlog():
    pump = ReviewPump(multiplier=4.0) # 7 days
    # 1000 debt, 0 tomorrow liability -> target should be 142
    target = pump.calculate_target(current_debt=1000, tomorrow_liability=0)
    assert target == 142

def test_blitz_lever_clears_half_backlog():
    pump = ReviewPump(multiplier=7.0) # 2 days
    target = pump.calculate_target(current_debt=1000, tomorrow_liability=50)
    assert target == 550 # 500 (half debt) + 50 (liability)

def test_pump_status_cavitation():
    pump = ReviewPump(multiplier=1.0)
    status = pump.get_status(current_debt=1000, tomorrow_liability=100, daily_completions=50)
    assert status["status"] == "cavitation"

def test_pump_status_turbulent():
    pump = ReviewPump(multiplier=2.0) # 14 days -> target ~71 for 1000 debt
    status = pump.get_status(current_debt=1000, tomorrow_liability=0, daily_completions=100)
    assert status["status"] == "turbulent"
