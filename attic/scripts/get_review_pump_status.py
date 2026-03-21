import asyncio
import json
from services.review_pump import ReviewPump
from services.neon_sync_checker import NeonSyncChecker
from beeminder_client import BeeminderClient
from datetime import datetime

async def main():
    neon = NeonSyncChecker()
    beeminder = BeeminderClient()
    
    # 1. Get stats from Neon
    db_stats = neon.get_language_stats()
    
    # 2. Get today's completions
    lang_goals = {"arabic": "reviewstack", "greek": "reviewstack-greek"}
    completions = {}
    for lang, slug in lang_goals.items():
        try:
            datapoints = await beeminder.get_datapoints(slug)
            today_str = datetime.now().strftime("%Y-%m-%d")
            completions[lang] = sum(float(dp["value"]) for dp in datapoints if dp["daystamp"] == today_str)
        except Exception:
            completions[lang] = 0

    results = {}
    for lang, stats in db_stats.items():
        current_debt = stats.get("current", 0)
        tomorrow_liability = stats.get("tomorrow", 0)
        multiplier = stats.get("multiplier", 1.0)
        daily_done = completions.get(lang, 0)
        
        pump = ReviewPump(multiplier=multiplier)
        pump_status = pump.get_status(current_debt, tomorrow_liability, daily_done)
        results[lang] = pump_status
        
    print(json.dumps(results, indent=2))
    await beeminder.close()

if __name__ == "__main__":
    asyncio.run(main())
