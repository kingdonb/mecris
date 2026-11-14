import asyncio
import traceback
import sys
from beeminder_client import BeeminderClient

async def test():
    client = BeeminderClient()
    try:
        goals = await client.get_all_goals()
        print(f"Found {len(goals)} goals")
    except Exception as e:
        traceback.print_exc()

asyncio.run(test())
