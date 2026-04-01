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

def test_system_overdrive():
    # 10.0x (1 day)
    pump = ReviewPump(multiplier=10.0)
    assert pump.calculate_target(100, 10) == 110 # 10 + 100/1
    status = pump.get_status(100, 10, 50)
    assert status["lever_name"] == "System Overdrive"
    assert status["target_flow_rate"] == 60  # remaining: 110 target - 50 completions

def test_goal_met_when_debt_rounds_to_zero_target_with_aggressive_multiplier():
    # Fix: 5cb1397 — debt so small it rounds to 0 per day with 14-day window.
    # Before fix: goal_met = (current_debt == 0) = False (false negative).
    # After fix: multiplier > 1.0 and debt > 0 → goal_met = (completions >= 0) = True.
    pump = ReviewPump(multiplier=2.0)  # 14 days
    status = pump.get_status(current_debt=5, tomorrow_liability=0, daily_completions=0)
    assert status["goal_met"] is True

def test_goal_met_false_in_maintenance_mode_with_outstanding_debt():
    # Maintenance (1.0x) sets target = tomorrow_liability only. With tomorrow=0,
    # target=0 and multiplier is NOT > 1.0, so goal_met = (current_debt == 0) = False.
    pump = ReviewPump(multiplier=1.0)
    status = pump.get_status(current_debt=500, tomorrow_liability=0, daily_completions=0)
    assert status["goal_met"] is False
