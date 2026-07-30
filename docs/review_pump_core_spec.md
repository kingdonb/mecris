# ReviewPump Core Shared Function — Priority 2 Spec

## Problem Statement

Android `ReviewPumpCalculator.kt` and Python `ReviewPump` (in `services/review_pump.py`) diverge:

| Feature | Android | Python Server |
|---------|---------|---------------|
| `calculateTargetFlowRate()` | ✅ | ✅ |
| `calculateDebtCoverageRatio()` | ✅ | ❌ |
| `calculateFlowFillRatio()` | ✅ | ❌ |
| `calculateIsPlayMode()` | ✅ | ❌ |
| `calculateBeckonSignal()` | ✅ | ❌ |
| `calculateGoalMet()` | ✅ | ✅ (different logic) |
| **Greek `min_target=100` baseline** | ❌ hardcoded in UI | ✅ in `get_status()` |

**Consequence**: Greek shows "0 target" on Android until debt > 0, while server correctly shows 100. Play mode, beckon signal, debt coverage — Android-only.

---

## Solution: Shared Pure-Python Core + KMP Port

### 1. New Module: `services/review_pump_core.py`

```python
"""Single source of truth for ReviewPump math. No I/O, no config, pure functions."""

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


@dataclass(frozen=True)
class PumpInput:
    current_debt: int           # outstanding reviews (cards or points)
    tomorrow_liability: int     # reviews due tomorrow
    daily_completions: int      # cards/points completed today
    multiplier: float           # lever value
    min_target: int = 0         # baseline (Greek=100, Arabic=0)


@dataclass(frozen=True)
class PumpOutput:
    target_flow_rate: int       # today's quota
    target_flow_rate_remaining: int  # max(0, target - daily_completions)
    goal_met: bool
    status: str                 # "cavitation" | "laminar" | "turbulent"
    debt_coverage_ratio: float  # daily_completions / current_debt (0 if no debt)
    flow_fill_ratio: float      # daily_completions / target_flow_rate (capped 1.0)
    is_play_mode: bool          # debt > target * 7
    beckon_signal: bool         # debt >= 300
    lever_name: str


def clearance_days(multiplier: float) -> Optional[int]:
    return LEVER_CONFIG.get(multiplier, {}).get("days")


def lever_name(multiplier: float) -> str:
    return LEVER_CONFIG.get(multiplier, {}).get("name", "Custom")


def calculate_target_flow_rate(inp: PumpInput) -> int:
    """Core formula: tomorrow_liability + current_debt / clearance_days (floor)."""
    days = clearance_days(inp.multiplier)
    backlog = inp.current_debt / days if days else 0
    target = inp.tomorrow_liability + int(backlog)
    return max(target, inp.min_target)


def calculate_goal_met(inp: PumpInput, target_flow_rate: int) -> bool:
    if inp.current_debt == 0 and inp.tomorrow_liability == 0:
        return True
    return inp.daily_completions >= target_flow_rate


def calculate_debt_coverage_ratio(inp: PumpInput) -> float:
    if inp.current_debt <= 0:
        return 0.0
    return min(inp.daily_completions / inp.current_debt, 1.0)


def calculate_flow_fill_ratio(inp: PumpInput, target_flow_rate: int) -> float:
    if target_flow_rate <= 0:
        return 0.0
    return min(inp.daily_completions / target_flow_rate, 1.0)


def calculate_is_play_mode(inp: PumpInput, target_flow_rate: int) -> bool:
    if target_flow_rate <= 0:
        return False
    return inp.current_debt > target_flow_rate * 7


def calculate_beckon_signal(inp: PumpInput) -> bool:
    return inp.current_debt >= 300


def calculate_status(inp: PumpInput, target_flow_rate: int) -> str:
    if inp.current_debt == 0 and inp.tomorrow_liability == 0:
        return "laminar"
    if inp.daily_completions < inp.tomorrow_liability:
        return "cavitation"
    if target_flow_rate > 0 and inp.daily_completions >= target_flow_rate:
        return "turbulent"
    return "laminar"


def run_pump(inp: PumpInput) -> PumpOutput:
    target = calculate_target_flow_rate(inp)
    return PumpOutput(
        target_flow_rate=target,
        target_flow_rate_remaining=max(0, target - inp.daily_completions),
        goal_met=calculate_goal_met(inp, target),
        status=calculate_status(inp, target),
        debt_coverage_ratio=calculate_debt_coverage_ratio(inp),
        flow_fill_ratio=calculate_flow_fill_ratio(inp, target),
        is_play_mode=calculate_is_play_mode(inp, target),
        beckon_signal=calculate_beckon_signal(inp),
        lever_name=lever_name(inp.multiplier),
    )
```

### 2. Python Server — `services/review_pump.py`

```python
from services.review_pump_core import run_pump, PumpInput

class ReviewPump:
    def __init__(self, multiplier: float = 1.0):
        self.multiplier = multiplier

    def get_status(self, current_debt: int, tomorrow_liability: int,
                   daily_completions: int, unit: str = "points",
                   min_target: int = 0) -> dict:
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
            "current_flow_rate": inp.daily_completions,
            "goal_met": out.goal_met,
            "status": out.status,
            "debt_remaining": inp.current_debt,
            "unit": unit,
            # NEW fields for Android parity
            "debt_coverage_ratio": out.debt_coverage_ratio,
            "flow_fill_ratio": out.flow_fill_ratio,
            "is_play_mode": out.is_play_mode,
            "beckon_signal": out.beckon_signal,
        }
```

### 3. MCP Tool `get_language_velocity_stats` (in `mcp_server.py`)

Add new fields to each language's returned dict:
```python
"debt_coverage_ratio": pump_status.get("debt_coverage_ratio", 0.0),
"flow_fill_ratio": pump_status.get("flow_fill_ratio", 0.0),
"is_play_mode": pump_status.get("is_play_mode", False),
"beckon_signal": pump_status.get("beckon_signal", False),
```

### 4. Android — Kotlin Port

Create `ReviewPumpCore.kt` mirroring `review_pump_core.py` 1:1 (pure functions, same `PumpInput`/`PumpOutput` data classes). `ReviewPumpCalculator` becomes a thin wrapper.

### 5. Tests

| Test | Location |
|------|----------|
| Core formula parity (Python vs Kotlin) | `tests/test_review_pump_core.py` |
| Greek `min_target=100` baseline | `tests/test_review_pump_core.py::test_greek_baseline` |
| Status transitions (cavitation→laminar→turbulent) | `tests/test_review_pump_core.py` |
| Play mode threshold (debt > 7×target) | `tests/test_review_pump_core.py` |
| Beckon signal at 300 | `tests/test_review_pump_core.py` |

---

## Acceptance Criteria

1. `services/review_pump_core.py` exists, 100% pure functions, no imports beyond stdlib.
2. Python `ReviewPump.get_status()` returns all 11 fields above.
3. Android `ReviewPumpCore` produces **identical** `PumpOutput` for identical `PumpInput` (verified by shared test vectors).
4. Greek language shows `absolute_target=100` when `current_debt=0, tomorrow_liability=0` on both platforms.
5. All new unit tests pass.
6. No behavioral change for Arabic (min_target=0) or existing callers.

---

## Out of Scope

- Cloud Pump WASM component (`poc/wasm/review-pump-py/`) — separate sync later.
- UI rendering of new fields (Android dashboard already has placeholders).
- Beeminder sync logic — unchanged.