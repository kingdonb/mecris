import os
import asyncio
from beeminder_client import BeeminderClient
from dotenv import load_dotenv

load_dotenv()

async def check():
    client = BeeminderClient()
    try:
        datapoints = await client.get_goal_datapoints('bike')
        print(f"Total Datapoints: {len(datapoints)}")
        if datapoints:
            latest = datapoints[0]
            print(f"Latest Datapoint: {latest.get('updated_at')} - {latest.get('comment')}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check())
