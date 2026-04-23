"""
review-pump-py WASM component — app.py (POC for kingdonb/mecris#157)

HTTP handler: POST /internal/review-pump-status
Body JSON: {
  "debt": <i32>,
  "tomorrow_liability": <i32>,
  "daily_completions": <i32>,
  "multiplier_x10": <u32>,    # integer tenths: 10=1.0x, 20=2.0x, 100=10.0x
  "unit": <string>             # "points" | "cards"
}
Returns JSON: PumpStatus object

This is the Python-native WASM migration path (zero Rust rewrite) for
ReviewPump, as described in LOGIC_VACUUMING_CANDIDATES.md Candidate 1 and
the kingdonb/mecris#157 "Holy Grail" architectural directive.

Implementation: componentize-py + spin_sdk HTTP incoming-handler.

Build:
    pip install -r requirements.txt && spin py2wasm app -o review-pump-py.wasm

The pure-logic functions (calculate_target, get_status, etc.) are
self-contained and importable in tests without the WASM runtime.
The IncomingHandler class requires spin_sdk which is only present inside
the compiled WASM component — it is guarded by try/except ImportError.

Multiplier encoding (integer tenths, matching the Rust review-pump and WIT spec):
  10  → 1.0x  Maintenance
  20  → 2.0x  Steady
  30  → 3.0x  Brisk
  40  → 4.0x  Aggressive
  50  → 5.0x  High Pressure
  60  → 6.0x  Very High
  70  → 7.0x  The Blitz
 100  → 10.0x System Overdrive
"""

import json
import logging

logger = logging.getLogger("mecris.review_pump_component")

# ---------------------------------------------------------------------------
# Static lever config table.
# Key: multiplier × 10 (integer tenths to avoid IEEE 754 hazards in equality checks)
# Value: (lever_name, clearance_days_or_None)
# ---------------------------------------------------------------------------
_LEVER_CONFIG = {
    10: ("Maintenance", None),
    20: ("Steady", 14),
    30: ("Brisk", 10),
    40: ("Aggressive", 7),
    50: ("High Pressure", 5),
    60: ("Very High", 3),
    70: ("The Blitz", 2),
    100: ("System Overdrive", 1),
}

# Max points awarded per correctly answered Arabic hard card.
ARABIC_POINTS_PER_CARD = 16


def _lookup(multiplier_x10: int) -> tuple:
    """Return (lever_name, days_or_None) for a given integer-tenths multiplier."""
    return _LEVER_CONFIG.get(multiplier_x10, ("Maintenance", None))


def calculate_target(debt: int, tomorrow_liability: int, multiplier_x10: int) -> int:
    """
    Calculate the daily target completions.

    Formula: tomorrow_liability + (debt / clearance_days)
    In Maintenance mode (days=None), target = tomorrow_liability (no debt clearing).
    """
    _, days = _lookup(multiplier_x10)
    if days is None:
        return tomorrow_liability
    return tomorrow_liability + (debt // days)


def get_status(
    debt: int,
    tomorrow_liability: int,
    daily_completions: int,
    multiplier_x10: int,
    unit: str = "points",
) -> dict:
    """
    Return full pump status including flow-state classification.

    Flow states:
      cavitation  — daily_completions < tomorrow_liability (falling behind baseline)
      turbulent   — daily_completions >= target AND target > 0 (ahead of schedule)
      laminar     — otherwise (normal healthy flow)
    """
    lever_name, _ = _lookup(multiplier_x10)
    target = calculate_target(debt, tomorrow_liability, multiplier_x10)

    if debt == 0 and tomorrow_liability == 0:
        target = 0
        status = "laminar"
        goal_met = True
    else:
        if daily_completions < tomorrow_liability:
            status = "cavitation"
        elif target > 0 and daily_completions >= target:
            status = "turbulent"
        else:
            status = "laminar"

        if target > 0 or (debt > 0 and multiplier_x10 > 10):
            goal_met = daily_completions >= target
        else:
            goal_met = debt == 0

    return {
        "multiplier_x10": multiplier_x10,
        "lever_name": lever_name,
        "target_flow_rate": max(0, target - daily_completions),
        "current_flow_rate": daily_completions,
        "goal_met": goal_met,
        "status": status,
        "debt_remaining": debt,
        "unit": unit,
    }


def _parse_request(body_bytes: bytes) -> dict:
    """Parse JSON request body. Returns dict with defaults for missing fields."""
    try:
        data = json.loads(body_bytes or b"{}")
    except (json.JSONDecodeError, ValueError):
        data = {}
    return {
        "debt": int(data.get("debt", 0)),
        "tomorrow_liability": int(data.get("tomorrow_liability", 0)),
        "daily_completions": int(data.get("daily_completions", 0)),
        "multiplier_x10": int(data.get("multiplier_x10", 10)),
        "unit": str(data.get("unit", "points")),
    }


def _json_ok(status_dict: dict) -> bytes:
    """Serialize a pump status dict to JSON bytes."""
    return json.dumps(status_dict).encode()


def _error_json(message: str) -> bytes:
    """Serialize an error message to JSON bytes."""
    return json.dumps({"error": message}).encode()


# ---------------------------------------------------------------------------
# HTTP handler — operational inside the WASM runtime only.
# All pure logic above is importable in tests without the WASM runtime.
# ---------------------------------------------------------------------------
try:
    from spin_sdk.http import IncomingHandler as _SpinHandler, Request, Response

    class IncomingHandler(_SpinHandler):
        """Spin HTTP handler for POST /internal/review-pump-status."""

        def handle(self, request: Request) -> Response:
            try:
                params = _parse_request(request.body)
                result = get_status(
                    debt=params["debt"],
                    tomorrow_liability=params["tomorrow_liability"],
                    daily_completions=params["daily_completions"],
                    multiplier_x10=params["multiplier_x10"],
                    unit=params["unit"],
                )
                return Response(
                    200,
                    {"content-type": "application/json"},
                    _json_ok(result),
                )
            except Exception as exc:
                logger.error(f"review_pump_py component error: {exc}")
                return Response(
                    500,
                    {"content-type": "application/json"},
                    _error_json("internal error"),
                )

    def handle_request(request):
        """Top-level entry point for spin py2wasm."""
        return IncomingHandler().handle(request)

except ImportError:
    # Fail gracefully outside WASM runtime
    def handle_request(request):
        raise NotImplementedError("handle_request requires WASM runtime (spin_sdk)")
