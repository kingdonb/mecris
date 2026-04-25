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
"""

import json
import logging
from spin_sdk import http
from spin_sdk.http import Request, Response

logger = logging.getLogger("mecris.review_pump_component")

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

ARABIC_POINTS_PER_CARD = 16

def _lookup(multiplier_x10: int) -> tuple:
    return _LEVER_CONFIG.get(multiplier_x10, ("Maintenance", None))

def calculate_target(debt: int, tomorrow_liability: int, multiplier_x10: int) -> int:
    _, days = _lookup(multiplier_x10)
    if days is None:
        return tomorrow_liability
    return tomorrow_liability + (debt // days)

def get_status(debt: int, tomorrow_liability: int, daily_completions: int, multiplier_x10: int, unit: str = "points") -> dict:
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

class HttpHandler(http.Handler):
    async def handle_request(self, request: Request) -> Response:
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
                json.dumps(result).encode(),
            )
        except Exception as exc:
            print(f"review_pump_py component error: {exc}")
            return Response(
                500,
                {"content-type": "application/json"},
                json.dumps({"error": "internal error"}).encode(),
            )

# Mandatory export for spin-sdk v4
incoming_handler = HttpHandler()
