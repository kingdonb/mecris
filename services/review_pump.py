"""
ReviewPump — Python wrapper around the pure core logic.

The canonical math lives in `services.review_pump_core`.
This class provides a backward-compatible interface for existing callers
and adds the `ARABIC_POINTS_PER_CARD` constant used by the language sync.
"""
from typing import Dict, Any

from services.review_pump_core import (
    PumpInput,
    PumpOutput,
    run_pump,
    clearance_days,
    lever_name,
    LEVER_CONFIG,
)

# Max points awarded per correctly answered Arabic hard card.
# Using the max (16) rather than the average (12) prevents
# the Nag Engine from prematurely marking the Arabic goal "done"
# when only easy/new cards were played (kingdonb/mecris#151).
ARABIC_POINTS_PER_CARD = 16


class ReviewPump:
    """
    ReviewPump logic for calculating daily language targets based on a multiplier lever.

    Delegates to `services.review_pump_core.run_pump` for all math.
    """

    def __init__(self, multiplier: float = 1.0):
        # Validate multiplier against known config; default to 1.0
        if multiplier not in LEVER_CONFIG:
            self.multiplier = 1.0
        else:
            self.multiplier = multiplier

    def calculate_target(self, current_debt: int, tomorrow_liability: int) -> int:
        """
        Calculates the daily target completions.
        Formula: tomorrow_liability + floor(current_debt / clearance_days)
        """
        days = clearance_days(self.multiplier)
        if days is None:
            return tomorrow_liability
        backlog_portion = current_debt / days
        return int(tomorrow_liability + backlog_portion)

    def get_status(
        self,
        current_debt: int,
        tomorrow_liability: int,
        daily_completions: int,
        unit: str = "points",
        min_target: int = 0,
    ) -> Dict[str, Any]:
        """
        Returns a status dictionary for the pump including target and flow state.

        Now includes Android-parity fields:
        - debt_coverage_ratio
        - flow_fill_ratio
        - is_play_mode
        - beckon_signal
        """
        inp = PumpInput(
            current_debt=current_debt,
            tomorrow_liability=tomorrow_liability,
            daily_completions=daily_completions,
            multiplier=self.multiplier,
            min_target=min_target,
        )
        out = run_pump(inp)

        return {
            "multiplier": self.multiplier,
            "lever_name": out.lever_name,
            "absolute_target": out.target_flow_rate,
            "target_flow_rate": out.target_flow_rate_remaining,
            "current_flow_rate": out.current_flow_rate,
            "goal_met": out.goal_met,
            "status": out.status,
            "debt_remaining": out.debt_remaining,
            "unit": unit,
            # New fields for Android parity (review_pump_core parity)
            "debt_coverage_ratio": out.debt_coverage_ratio,
            "flow_fill_ratio": out.flow_fill_ratio,
            "is_play_mode": out.is_play_mode,
            "beckon_signal": out.beckon_signal,
        }