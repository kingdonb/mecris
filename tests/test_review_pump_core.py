"""
Tests for ReviewPump Core — pure math, no I/O.
Verifies formula parity, edge cases, and Greek/Arabic baselines.
"""
import pytest
from services.review_pump_core import (
    PumpInput,
    PumpOutput,
    clearance_days,
    lever_name,
    calculate_target_flow_rate,
    calculate_goal_met,
    calculate_debt_coverage_ratio,
    calculate_flow_fill_ratio,
    calculate_is_play_mode,
    calculate_beckon_signal,
    calculate_status,
    run_pump,
    LEVER_CONFIG,
)


class TestClearanceDays:
    def test_maintenance_returns_none(self):
        assert clearance_days(1.0) is None

    def test_known_levers(self):
        assert clearance_days(2.0) == 14
        assert clearance_days(4.0) == 7
        assert clearance_days(7.0) == 2
        assert clearance_days(10.0) == 1

    def test_unknown_returns_none(self):
        assert clearance_days(99.0) is None


class TestLeverName:
    def test_known_names(self):
        assert lever_name(1.0) == "Maintenance"
        assert lever_name(4.0) == "Aggressive"
        assert lever_name(10.0) == "System Overdrive"

    def test_unknown_returns_custom(self):
        assert lever_name(99.0) == "Custom"


class TestCalculateTargetFlowRate:
    def test_maintenance_only_tomorrow(self):
        """1.0 multiplier = no backlog clearance, target = tomorrow only."""
        inp = PumpInput(current_debt=1000, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_target_flow_rate(inp) == 50

    def test_aggressive_clears_backlog(self):
        """4.0 multiplier = 7 days, 1000 debt -> 142/day backlog + tomorrow."""
        inp = PumpInput(current_debt=1000, tomorrow_liability=50, daily_completions=0,
                        multiplier=4.0, min_target=0)
        assert calculate_target_flow_rate(inp) == 50 + 142  # 192

    def test_greek_min_target_baseline(self):
        """Greek min_target=100 ensures baseline even with zero debt."""
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=100)
        assert calculate_target_flow_rate(inp) == 100

    def test_arabic_min_target_zero(self):
        """Arabic min_target=0 allows zero target when caught up."""
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_target_flow_rate(inp) == 0

    def test_min_target_floor_respected(self):
        """Target never below min_target even if formula yields less."""
        inp = PumpInput(current_debt=10, tomorrow_liability=5, daily_completions=0,
                        multiplier=1.0, min_target=100)
        assert calculate_target_flow_rate(inp) == 100

    def test_large_debt_aggressive(self):
        """Large debt with aggressive lever."""
        inp = PumpInput(current_debt=5000, tomorrow_liability=200, daily_completions=0,
                        multiplier=4.0, min_target=0)
        # 5000/7 = 714 + 200 = 914
        assert calculate_target_flow_rate(inp) == 914


class TestCalculateGoalMet:
    def test_vacuous_success_no_debt_no_liability(self):
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_goal_met(inp, 0) is True

    def test_met_exactly_at_target(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=150,
                        multiplier=1.0, min_target=0)
        assert calculate_goal_met(inp, 150) is True

    def test_met_above_target(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=200,
                        multiplier=1.0, min_target=0)
        assert calculate_goal_met(inp, 150) is True

    def test_not_met_below_target(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=100,
                        multiplier=1.0, min_target=0)
        assert calculate_goal_met(inp, 150) is False


class TestCalculateDebtCoverageRatio:
    def test_zero_debt_returns_zero(self):
        inp = PumpInput(current_debt=0, tomorrow_liability=50, daily_completions=100,
                        multiplier=1.0, min_target=0)
        assert calculate_debt_coverage_ratio(inp) == 0.0

    def test_partial_coverage(self):
        inp = PumpInput(current_debt=1000, tomorrow_liability=50, daily_completions=250,
                        multiplier=1.0, min_target=0)
        assert calculate_debt_coverage_ratio(inp) == 0.25

    def test_full_coverage_capped_at_one(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=150,
                        multiplier=1.0, min_target=0)
        assert calculate_debt_coverage_ratio(inp) == 1.0


class TestCalculateFlowFillRatio:
    def test_zero_target_returns_zero(self):
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=100,
                        multiplier=1.0, min_target=0)
        assert calculate_flow_fill_ratio(inp, 0) == 0.0

    def test_partial_fill(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=75,
                        multiplier=1.0, min_target=0)
        assert calculate_flow_fill_ratio(inp, 150) == 0.5

    def test_full_fill_capped_at_one(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=200,
                        multiplier=1.0, min_target=0)
        assert calculate_flow_fill_ratio(inp, 150) == 1.0


class TestCalculateIsPlayMode:
    def test_false_when_no_target(self):
        inp = PumpInput(current_debt=1000, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_is_play_mode(inp, 0) is False

    def test_false_when_debt_below_threshold(self):
        inp = PumpInput(current_debt=500, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_is_play_mode(inp, 100) is False  # 500 < 100*7

    def test_true_when_debt_exceeds_week_of_targets(self):
        inp = PumpInput(current_debt=800, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_is_play_mode(inp, 100) is True  # 800 > 100*7


class TestCalculateBeckonSignal:
    def test_false_below_300(self):
        inp = PumpInput(current_debt=299, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_beckon_signal(inp) is False

    def test_true_at_300(self):
        inp = PumpInput(current_debt=300, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_beckon_signal(inp) is True

    def test_true_above_300(self):
        inp = PumpInput(current_debt=500, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_beckon_signal(inp) is True


class TestCalculateStatus:
    def test_cavitation_below_tomorrow_liability(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=30,
                        multiplier=1.0, min_target=0)
        assert calculate_status(inp, 50) == "cavitation"

    def test_turbulent_at_or_above_target(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=50,
                        multiplier=1.0, min_target=0)
        assert calculate_status(inp, 50) == "turbulent"

    def test_laminar_between_liability_and_target(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=50,
                        multiplier=4.0, min_target=0)  # target = 50 + 14 = 64
        assert calculate_status(inp, 64) == "laminar"

    def test_vacuous_laminar_no_debt_no_liability(self):
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=0)
        assert calculate_status(inp, 0) == "laminar"


class TestRunPumpIntegration:
    def test_arabic_maintenance_caught_up(self):
        """Arabic: 0 debt, 0 liability, maintenance -> 0 target, goal met."""
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=0)
        out = run_pump(inp)
        assert out.target_flow_rate == 0
        assert out.goal_met is True
        assert out.status == "laminar"
        assert out.target_flow_rate_remaining == 0

    def test_arabic_maintenance_with_debt(self):
        """Arabic: 2600 debt, maintenance (1.0) -> target = tomorrow only."""
        inp = PumpInput(current_debt=2600, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        out = run_pump(inp)
        assert out.target_flow_rate == 50
        assert out.goal_met is False
        assert out.status == "cavitation"
        assert out.debt_coverage_ratio == 0.0

    def test_greek_baseline_min_target(self):
        # Greek: min_target=100, no debt, no liability -> target=100
        # With no debt and no liability, goal_met is True (vacuous success)
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=0,
                        multiplier=1.0, min_target=100)
        out = run_pump(inp)
        assert out.target_flow_rate == 100
        assert out.goal_met is True  # vacuous success: no debt, no liability
        assert out.target_flow_rate_remaining == 100
        assert out.flow_fill_ratio == 0.0

    def test_greek_met_at_100(self):
        """Greek: 0 debt, 0 liability, min_target=100, 100 completions -> met."""
        inp = PumpInput(current_debt=0, tomorrow_liability=0, daily_completions=100,
                        multiplier=1.0, min_target=100)
        out = run_pump(inp)
        assert out.goal_met is True
        assert out.flow_fill_ratio == 1.0

    def test_aggressive_with_backlog(self):
        """4.0 lever, 1000 debt, 50 tomorrow -> target 192."""
        inp = PumpInput(current_debt=1000, tomorrow_liability=50, daily_completions=0,
                        multiplier=4.0, min_target=0)
        out = run_pump(inp)
        assert out.target_flow_rate == 192  # 50 + 1000/7=142
        assert out.debt_coverage_ratio == 0.0
        assert out.is_play_mode is False  # 1000 > 192*7=1344? No, 1000 < 1344

    def test_play_mode_trigger(self):
        """Large debt triggers play mode."""
        inp = PumpInput(current_debt=2000, tomorrow_liability=50, daily_completions=0,
                        multiplier=4.0, min_target=0)
        out = run_pump(inp)
        # target = 50 + 2000/7 = 50 + 285 = 335
        # 2000 > 335*7 = 2345? No -> False
        # Let's use even larger debt
        inp2 = PumpInput(current_debt=3000, tomorrow_liability=50, daily_completions=0,
                         multiplier=4.0, min_target=0)
        out2 = run_pump(inp2)
        # target = 50 + 3000/7 = 50 + 428 = 478
        # 3000 > 478*7 = 3346? No -> False
        # Actually need debt > target*7
        # target = tomorrow + debt/days
        # debt > (tomorrow + debt/days)*7
        # debt > 7*tomorrow + 7*debt/days
        # debt*(1 - 7/days) > 7*tomorrow
        # For days=7: debt*0 > 7*tomorrow -> never true
        # For days=3 (6.0): debt*(1-7/3) = debt*(-4/3) > 7*tomorrow -> never true
        # For days=2 (7.0): debt*(1-3.5) = debt*(-2.5) > 7*tomorrow -> never true
        # For days=1 (10.0): debt*(1-7) = -6*debt > 7*tomorrow -> never true
        # So play_mode only triggers for days > 7 (i.e., multiplier 2.0=14 days, 3.0=10 days)
        inp3 = PumpInput(current_debt=2000, tomorrow_liability=50, daily_completions=0,
                         multiplier=2.0, min_target=0)  # 14 days
        out3 = run_pump(inp3)
        # target = 50 + 2000/14 = 50 + 142 = 192
        # 2000 > 192*7 = 1344 -> True
        assert out3.is_play_mode is True

    def test_beckon_signal_at_300(self):
        inp = PumpInput(current_debt=300, tomorrow_liability=50, daily_completions=0,
                        multiplier=1.0, min_target=0)
        out = run_pump(inp)
        assert out.beckon_signal is True

    def test_all_levers_produce_valid_output(self):
        """Every defined lever should produce a valid PumpOutput."""
        for mult in LEVER_CONFIG.keys():
            inp = PumpInput(current_debt=100, tomorrow_liability=10, daily_completions=5,
                            multiplier=mult, min_target=0)
            out = run_pump(inp)
            assert isinstance(out, PumpOutput)
            assert out.target_flow_rate >= 0
            assert out.status in ("cavitation", "laminar", "turbulent")
            assert 0.0 <= out.debt_coverage_ratio <= 1.0
            assert 0.0 <= out.flow_fill_ratio <= 1.0
            assert isinstance(out.is_play_mode, bool)
            assert isinstance(out.beckon_signal, bool)
            assert out.lever_name == LEVER_CONFIG[mult]["name"]


class TestPropertyInvariants:
    """Property-based style invariants that must always hold."""

    def test_target_flow_rate_never_negative(self):
        for mult in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0]:
            for debt in [0, 10, 100, 1000, 10000]:
                for tomorrow in [0, 10, 100]:
                    inp = PumpInput(current_debt=debt, tomorrow_liability=tomorrow,
                                    daily_completions=0, multiplier=mult, min_target=0)
                    out = run_pump(inp)
                    assert out.target_flow_rate >= 0

    def test_goal_met_implies_flow_fill_ratio_at_least_1(self):
        for mult in [1.0, 2.0, 4.0, 10.0]:
            inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=200,
                            multiplier=mult, min_target=0)
            out = run_pump(inp)
            if out.goal_met:
                assert out.flow_fill_ratio >= 1.0 - 1e-9  # floating point

    def test_cavitation_implies_below_tomorrow_liability(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=30,
                        multiplier=1.0, min_target=0)
        out = run_pump(inp)
        assert out.status == "cavitation"
        assert inp.daily_completions < inp.tomorrow_liability

    def test_turbulent_implies_at_or_above_target(self):
        inp = PumpInput(current_debt=100, tomorrow_liability=50, daily_completions=50,
                        multiplier=1.0, min_target=0)
        out = run_pump(inp)
        assert out.status == "turbulent"
        assert inp.daily_completions >= out.target_flow_rate