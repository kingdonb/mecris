"""
ReviewPump Core — Pure Python math for language review velocity calculations.

Single source of truth for both Python server and Android Kotlin port.
No I/O, no config, no side effects — only pure functions and dataclasses.
"""
from dataclasses import dataclass
from typing import Optional

LEVER_CONFIG = {
    1.0: {"name": "Maintenance", "days": None},
    2.0: {"name": "Steady", "days": 14},
    3.0: {"name": "Brisk", "days": 10},
    4.0: {"name": "Aggressive", "days": 7},
    5.0: {"name": "High Pressure", "days": 5},
    6.0: {"name": "Very High", "days": 3},
    7.0: {"name": "The Blitz", "days": 2},
    10.0: {"name": "System Overdrive", "days": 1},
}


@dataclass(frozen=True, slots=True)
class PumpInput:
    current_debt: int           # Outstanding reviews (cards or points)
    tomorrow_liability: int     # Reviews due tomorrow
    daily_completions: int      # Cards/points completed today
    multiplier: float           # Lever value (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0)
    min_target: int = 0         # Baseline floor (Greek=100, Arabic=0)


@dataclass(frozen=True, slots=True)
class PumpOutput:
    target_flow_rate: int               # Today's quota (tomorrow_liability + backlog portion)
    target_flow_rate_remaining: int     # max(0, target - daily_completions)
    current_flow_rate: int              # daily_completions (for backward compat)
    goal_met: bool
    status: str                         # "cavitation" | "laminar" | "turbulent"
    debt_coverage_ratio: float          # daily_completions / current_debt (0 if no debt, capped at 1.0)
    flow_fill_ratio: float              # daily_completions / target_flow_rate (capped at 1.0)
    is_play_mode: bool                  # debt > target * 7 (signal to play extra cards)
    beckon_signal: bool                 # debt >= 300 (signal to create Beeminder goal)
    lever_name: str
    debt_remaining: int                 # current_debt (backward compat alias)


def clearance_days(multiplier: float) -> Optional[int]:
    """Return clearance days for a given multiplier, or None for maintenance (1.0)."""
    return LEVER_CONFIG.get(multiplier, {}).get("days")


def lever_name(multiplier: float) -> str:
    """Return human-readable lever name."""
    return LEVER_CONFIG.get(multiplier, {}).get("name", "Custom")


def calculate_target_flow_rate(inp: PumpInput) -> int:
    """
    Core formula: tomorrow_liability + floor(current_debt / clearance_days)
    Floored at min_target (Greek=100, Arabic=0).
    """
    days = clearance_days(inp.multiplier)
    backlog = inp.current_debt / days if days else 0
    target = inp.tomorrow_liability + int(backlog)
    return max(target, inp.min_target)


def calculate_goal_met(inp: PumpInput, target_flow_rate: int) -> bool:
    """
    Goal met if:
    - No debt and no liability (vacuous success), OR
    - Target > 0 or (debt > 0 and multiplier > 1.0): daily_completions >= target
    - Else (target == 0 and multiplier <= 1.0): goal met only if no debt
    """
    if inp.current_debt == 0 and inp.tomorrow_liability == 0:
        return True
    if target_flow_rate > 0 or (inp.current_debt > 0 and inp.multiplier > 1.0):
        return inp.daily_completions >= target_flow_rate
    return inp.current_debt == 0


def calculate_debt_coverage_ratio(inp: PumpInput) -> float:
    """Fraction of outstanding debt covered by today's work. 0 if no debt, capped at 1.0."""
    if inp.current_debt <= 0:
        return 0.0
    return min(inp.daily_completions / inp.current_debt, 1.0)


def calculate_flow_fill_ratio(inp: PumpInput, target_flow_rate: int) -> float:
    """Fraction of today's target completed. 0 if no target, capped at 1.0."""
    if target_flow_rate <= 0:
        return 0.0
    return min(inp.daily_completions / target_flow_rate, 1.0)


def calculate_is_play_mode(inp: PumpInput, target_flow_rate: int) -> bool:
    """
    Play mode = outstanding debt exceeds one week of daily targets.
    Signals user should do extra cards beyond daily minimum.
    """
    if target_flow_rate <= 0:
        return False
    return inp.current_debt > target_flow_rate * 7


def calculate_beckon_signal(inp: PumpInput) -> bool:
    """
    Beckon signal = debt >= 300 cards.
    Suggests creating a Beeminder reviewstack goal for accountability.
    """
    return inp.current_debt >= 300


def calculate_status(inp: PumpInput, target_flow_rate: int) -> str:
    """
    Flow state:
    - cavitation: below tomorrow's liability (starved)
    - turbulent: at or above target flow rate (ahead)
    - laminar: between liability and target (steady)
    - (vacuous laminar if no debt/liability)
    """
    if inp.current_debt == 0 and inp.tomorrow_liability == 0:
        return "laminar"
    if inp.daily_completions < inp.tomorrow_liability:
        return "cavitation"
    if target_flow_rate > 0 and inp.daily_completions >= target_flow_rate:
        return "turbulent"
    return "laminar"


def run_pump(inp: PumpInput) -> PumpOutput:
    """Execute full pump calculation and return structured output."""
    target = calculate_target_flow_rate(inp)
    return PumpOutput(
        target_flow_rate=target,
        target_flow_rate_remaining=max(0, target - inp.daily_completions),
        current_flow_rate=inp.daily_completions,
        goal_met=calculate_goal_met(inp, target),
        status=calculate_status(inp, target),
        debt_coverage_ratio=calculate_debt_coverage_ratio(inp),
        flow_fill_ratio=calculate_flow_fill_ratio(inp, target),
        is_play_mode=calculate_is_play_mode(inp, target),
        beckon_signal=calculate_beckon_signal(inp),
        lever_name=lever_name(inp.multiplier),
        debt_remaining=inp.current_debt,
    )