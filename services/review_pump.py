from typing import Dict, Any, Optional

# Max points awarded per correctly answered Arabic hard card.
# Using the max (16) rather than the average (8+16)/2=12 prevents
# the Nag Engine from prematurely marking the Arabic goal "done"
# when only easy/new cards were played (kingdonb/mecris#151).
ARABIC_POINTS_PER_CARD = 16


class ReviewPump:
    """
    ReviewPump logic for calculating daily language targets based on a multiplier lever.
    """
    LEVER_CONFIG = {
        1.0: {"name": "Maintenance", "days": None},
        2.0: {"name": "Steady", "days": 14},
        3.0: {"name": "Brisk", "days": 10},
        4.0: {"name": "Aggressive", "days": 7}, # The Akrasia Horizon
        5.0: {"name": "High Pressure", "days": 5},
        6.0: {"name": "Very High", "days": 3},
        7.0: {"name": "The Blitz", "days": 2},
        10.0: {"name": "System Overdrive", "days": 1}
    }

    def __init__(self, multiplier: float = 1.0):
        # Default to 1.0 if not in config
        if multiplier not in self.LEVER_CONFIG:
            self.multiplier = 1.0
        else:
            self.multiplier = multiplier

    def calculate_target(self, current_debt: int, tomorrow_liability: int) -> int:
        """
        Calculates the daily target completions.
        Formula: tomorrow_liability + (current_debt / clearance_days)
        """
        config = self.LEVER_CONFIG.get(self.multiplier)
        days = config["days"]
        
        if days is None:
            return tomorrow_liability
        
        backlog_portion = current_debt / days
        return int(tomorrow_liability + backlog_portion)

    def get_status(self, current_debt: int, tomorrow_liability: int, daily_completions: int, unit: str = "points", min_target: int = 0) -> Dict[str, Any]:
        """
        Returns a status dictionary for the pump including target and flow state.
        """
        target = self.calculate_target(current_debt, tomorrow_liability)
        
        # Apply min_target baseline
        target = max(target, min_target)
        
        # Flow states: cavitation (low), laminar (normal), turbulent (high)
        status = "laminar"
        
        # If debt is zero and no liability, we are done.
        if current_debt == 0 and tomorrow_liability == 0:
            target = 0
            status = "laminar"
        elif daily_completions < tomorrow_liability:
            status = "cavitation"
        elif target > 0 and daily_completions >= target:
            status = "turbulent"
            
        return {
            "multiplier": self.multiplier,
            "lever_name": self.LEVER_CONFIG[self.multiplier]["name"],
            "absolute_target": target,
            "target_flow_rate": max(0, target - daily_completions),
            "current_flow_rate": daily_completions,
            "goal_met": daily_completions >= target if (target > 0 or (current_debt > 0 and self.multiplier > 1.0)) else (current_debt == 0),
            "status": status,
            "debt_remaining": current_debt,
            "unit": unit
        }
