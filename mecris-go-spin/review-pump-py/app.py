"""
Review Pump WASM component — app.py (Logic Vacuuming)

HTTP handler: POST /internal/review-pump-status
Body: {"debt": int, "tomorrow_liability": int, "daily_completions": int, "multiplier_x10": int, "unit": str}
Returns JSON mirroring the Rust review-pump status.

Implementation: componentize-py + spin_sdk HTTP incoming-handler.
"""

import json
import logging
from urllib.parse import urlparse

logger = logging.getLogger("mecris.review_pump_py_component")

class ReviewPump:
    """
    ReviewPump logic for calculating daily language targets based on a multiplier lever.
    """
    LEVER_CONFIG = {
        10: {"name": "Maintenance", "days": None},
        20: {"name": "Steady", "days": 14},
        30: {"name": "Brisk", "days": 10},
        40: {"name": "Aggressive", "days": 7},
        50: {"name": "High Pressure", "days": 5},
        60: {"name": "Very High", "days": 3},
        70: {"name": "The Blitz", "days": 2},
        100: {"name": "System Overdrive", "days": 1}
    }

    def __init__(self, multiplier_x10: int = 10):
        if multiplier_x10 not in self.LEVER_CONFIG:
            self.multiplier_x10 = 10
        else:
            self.multiplier_x10 = multiplier_x10

    def calculate_target(self, current_debt: int, tomorrow_liability: int) -> int:
        config = self.LEVER_CONFIG.get(self.multiplier_x10)
        days = config["days"]
        
        if days is None:
            return tomorrow_liability
        
        backlog_portion = current_debt / days
        return int(tomorrow_liability + backlog_portion)

    def get_status(self, current_debt: int, tomorrow_liability: int, daily_completions: int, unit: str = "points") -> dict:
        target = self.calculate_target(current_debt, tomorrow_liability)
        
        status = "laminar"
        
        if current_debt == 0 and tomorrow_liability == 0:
            target = 0
            status = "laminar"
            goal_met = True
        else:
            if daily_completions < tomorrow_liability:
                status = "cavitation"
            elif target > 0 and daily_completions >= target:
                status = "turbulent"
            
            # goal_met logic (mirrors Rust and Python exactly)
            if target > 0 or (current_debt > 0 and self.multiplier_x10 > 10):
                goal_met = daily_done >= target if 'daily_done' in locals() else daily_completions >= target
            else:
                goal_met = current_debt == 0
                
        return {
            "multiplier_x10": self.multiplier_x10,
            "lever_name": self.LEVER_CONFIG[self.multiplier_x10]["name"],
            "target_flow_rate": max(0, target - daily_completions),
            "current_flow_rate": daily_completions,
            "goal_met": goal_met,
            "status": status,
            "debt_remaining": current_debt,
            "unit": unit
        }

try:
    from spin_sdk.http import IncomingHandler as _SpinHandler, Request, Response

    class IncomingHandler(_SpinHandler):
        def handle(self, request: Request) -> Response:
            try:
                if request.method != "POST":
                    return Response(405, {"content-type": "application/json"}, json.dumps({"error": "Method Not Allowed"}).encode())
                
                body_bytes = request.body
                if not body_bytes:
                    return Response(400, {"content-type": "application/json"}, json.dumps({"error": "Missing request body"}).encode())
                
                req_data = json.loads(body_bytes.decode())
                
                debt = int(req_data.get("debt", 0))
                tomorrow = int(req_data.get("tomorrow_liability", 0))
                completions = int(req_data.get("daily_completions", 0))
                multiplier_x10 = int(req_data.get("multiplier_x10", 10))
                unit = req_data.get("unit", "points")
                
                pump = ReviewPump(multiplier_x10)
                status = pump.get_status(debt, tomorrow, completions, unit)
                
                return Response(200, {"content-type": "application/json"}, json.dumps(status).encode())
            except Exception as e:
                logger.error(f"review_pump_py HTTP handler error: {e}")
                return Response(500, {"content-type": "application/json"}, json.dumps({"error": "internal error"}).encode())

    def handle_request(request):
        return IncomingHandler().handle(request)

except ImportError:
    def handle_request(request):
        raise NotImplementedError("handle_request requires WASM runtime (spin_sdk)")
