"""
services/smart_nag.py — Success-pattern heuristic for walk nag suppression.

Implements kingdonb/mecris#200: suppress walk nags during high-probability
success windows and fire a catch-up nag when the window passes without activity.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

SUPPRESS_THRESHOLD = 0.70  # suppress nag if historical success rate exceeds this
HISTORY_DAYS = 30          # days of walk history to analyse
WINDOW_HOURS = 1           # success window is ±WINDOW_HOURS around each hour


def success_probability(
    walks: List[datetime],
    target_hour: int,
    now: Optional[datetime] = None,
) -> float:
    """Calculate the fraction of recent days on which the user walked within
    ±WINDOW_HOURS of target_hour.

    Denominator is always HISTORY_DAYS (30) to avoid inflated probabilities
    when the history is sparse.  Only walks from the last HISTORY_DAYS days
    are considered.

    Args:
        walks: Walk start datetimes (any timezone-naive datetimes).
        target_hour: Hour to centre the window on (0–23).
        now: Reference point for the history cutoff (defaults to datetime.now()).

    Returns:
        Float in [0.0, 1.0].
    """
    if not walks:
        return 0.0
    if now is None:
        now = datetime.now()

    cutoff = now - timedelta(days=HISTORY_DAYS)
    recent = [w for w in walks if w >= cutoff]
    if not recent:
        return 0.0

    window_start = (target_hour - WINDOW_HOURS) % 24
    window_end = (target_hour + WINDOW_HOURS) % 24
    wraps = window_start > window_end  # window crosses midnight

    walked_dates: set = set()
    for w in recent:
        h = w.hour
        in_window = (h >= window_start or h <= window_end) if wraps else (window_start <= h <= window_end)
        if in_window:
            walked_dates.add(w.date())

    return len(walked_dates) / HISTORY_DAYS


def find_peak_success_window(
    walks: List[datetime],
    now: Optional[datetime] = None,
) -> Tuple[int, float]:
    """Return the hour with the highest success probability.

    Returns:
        (peak_hour, peak_probability) where peak_hour == -1 and
        peak_probability == 0.0 when walks is empty or all probabilities are 0.
    """
    best_hour, best_prob = -1, 0.0
    for h in range(24):
        p = success_probability(walks, h, now=now)
        if p > best_prob:
            best_prob = p
            best_hour = h
    return best_hour, best_prob


def evaluate_nag(
    walks: List[datetime],
    current_hour: int,
    has_walked_today: bool,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Decide whether to suppress a walk nag or fire a catch-up nag.

    Algorithm:
    1. If the user has already walked today → suppress (nothing to do).
    2. If success_probability(current_hour) > SUPPRESS_THRESHOLD → suppress
       (the user will probably walk naturally; nagging would add noise).
    3. If the peak success window has passed without activity → catch-up nag
       (the "natural" window is gone; escalate now).
    4. Otherwise → do not suppress, do not catch-up (normal nag logic applies).

    Args:
        walks: Walk start datetimes from the last HISTORY_DAYS days.
        current_hour: Current local hour (0–23).
        has_walked_today: True if a qualifying walk is already logged today.
        now: Reference point for history cutoff (defaults to datetime.now()).

    Returns:
        Dict with keys:
            should_suppress (bool): True → skip the standard nag.
            catch_up_nag   (bool): True → fire an urgent catch-up message.
            probability    (float): Success rate at current_hour.
            reason         (str):  Human-readable rationale.
    """
    if has_walked_today:
        return {
            "should_suppress": True,
            "catch_up_nag": False,
            "probability": 0.0,
            "reason": "already walked today",
        }

    prob = success_probability(walks, current_hour, now=now)

    if prob > SUPPRESS_THRESHOLD:
        return {
            "should_suppress": True,
            "catch_up_nag": False,
            "probability": prob,
            "reason": (
                f"{prob:.0%} success rate near hour {current_hour} — "
                "suppressing nag (user will walk naturally)"
            ),
        }

    peak_hour, peak_prob = find_peak_success_window(walks, now=now)
    if peak_prob > SUPPRESS_THRESHOLD and peak_hour >= 0 and current_hour > peak_hour + WINDOW_HOURS:
        return {
            "should_suppress": False,
            "catch_up_nag": True,
            "probability": prob,
            "reason": (
                f"Success window (hour {peak_hour}, {peak_prob:.0%}) has passed "
                f"without activity — catch-up nag needed"
            ),
        }

    return {
        "should_suppress": False,
        "catch_up_nag": False,
        "probability": prob,
        "reason": (
            f"{prob:.0%} probability at hour {current_hour} — "
            "below suppression threshold"
        ),
    }
