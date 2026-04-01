import pytest
from services.review_pump import ReviewPump, ARABIC_POINTS_PER_CARD

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
    # Simulated Arabic goal logic from mcp_server.py — uses ARABIC_POINTS_PER_CARD (max, not average).
    # Using the max (16) prevents false "turbulent" early-switch bugs (kingdonb/mecris#151).
    points_today = 120
    daily_done_cards = int(points_today / ARABIC_POINTS_PER_CARD)
    assert daily_done_cards == 7  # 120/16=7, not 120/12=10 (which caused early-switch bug)

    pump = ReviewPump(multiplier=2.0)  # 14 days
    # 140 debt -> total target = 10 cards.
    # 120 points -> 7 estimated cards -> remaining = 10 - 7 = 3.
    # 120 points -> 7 estimated cards -> below target -> NOT turbulent (Arabic still needs work)
    status = pump.get_status(current_debt=140, tomorrow_liability=0, daily_completions=daily_done_cards, unit="cards")
    assert status["current_flow_rate"] == 7
    assert status["target_flow_rate"] == 3
    assert status["status"] != "turbulent"  # Not done: prevents premature switch to Greek
    assert status["unit"] == "cards"


def test_arabic_points_per_card_is_conservative():
    """ARABIC_POINTS_PER_CARD must equal 16 (max per hard card, not average 12).
    Using 12 triggers false 'turbulent' early-switch when Arabic isn't actually done
    (kingdonb/mecris#151). Using 16 requires earning more points before marking done."""
    assert ARABIC_POINTS_PER_CARD == 16


def test_arabic_early_switch_prevented():
    """120 pts with /16 gives 7 cards, below target of 10 → NOT turbulent (correct).
    With /12 it gives 10 cards = target → turbulent (early-switch bug).
    This test guards against regression back to the /12 divisor."""
    points_today = 120
    daily_done_cards = int(points_today / ARABIC_POINTS_PER_CARD)

    pump = ReviewPump(multiplier=2.0)  # 14-day clearance, debt=140 → target=10 cards
    status = pump.get_status(current_debt=140, tomorrow_liability=0, daily_completions=daily_done_cards, unit="cards")
    # With ARABIC_POINTS_PER_CARD=16: 7 cards < target 10 → not turbulent (correct)
    # With ARABIC_POINTS_PER_CARD=12: 10 cards = target 10 → turbulent (early-switch bug)
    assert status["status"] != "turbulent", (
        f"Arabic falsely marked done: {daily_done_cards} estimated cards at target "
        f"{status['target_flow_rate']}. ARABIC_POINTS_PER_CARD={ARABIC_POINTS_PER_CARD}"
    )
