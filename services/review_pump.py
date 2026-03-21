from typing import Dict, Any, Optional

class ReviewPump:
    """
    ReviewPump logic for calculating daily language targets based on a multiplier lever.
    """
    LEVER_CONFIG = {
        1.0: {"name": "Maintenance", "days": None},
        2.0: {"name": "Steady Progress", "days": 14},
        4.0: {"name": "Aggressive", "days": 5},
        10.0: {"name": "The Blitz", "days": 2}
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

    def get_status(self, current_debt: int, tomorrow_liability: int, daily_completions: int) -> Dict[str, Any]:
        """
        Returns a status dictionary for the pump including target and flow state.
        """
        target = self.calculate_target(current_debt, tomorrow_liability)
        
        # Flow states: cavitation (low), laminar (normal), turbulent (high)
        status = "laminar"
        if daily_completions < tomorrow_liability:
            status = "cavitation"
        elif daily_completions >= target and target > 0:
            status = "turbulent"
            
        return {
            "multiplier": self.multiplier,
            "lever_name": self.LEVER_CONFIG[self.multiplier]["name"],
            "target_flow_rate": target,
            "current_flow_rate": daily_completions,
            "status": status,
            "debt_remaining": current_debt
        }
