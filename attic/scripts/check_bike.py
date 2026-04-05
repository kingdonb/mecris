
import asyncio
import os
from datetime import datetime
from beeminder_client import BeeminderClient

async def main():
    client = BeeminderClient()
    goal_slug = "bike"
    print(f"Checking datapoints for '{goal_slug}'...")
    try:
        datapoints = await client.get_goal_datapoints(goal_slug, count=5)
        for dp in datapoints:
            ts = datetime.fromtimestamp(dp.get("timestamp", 0))
            print(f"Timestamp: {ts} | Value: {dp.get('value')} | Comment: {dp.get('comment')}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
