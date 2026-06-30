import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beeminder_client import BeeminderClient

async def main():
    load_dotenv()
    client = BeeminderClient(user_id="c0a81a4b-115a-4eb6-bc2c-40908c58bf64")
    goal_slug = "groqspend"
    
    print("=== CORRECTING MAY 31st DATAPOINT ===")
    
    # Delete the old 0.57 datapoint on May 31st
    old_id = "6a1c9482f0168a73d9b45619"
    print(f"Deleting old May 31st datapoint {old_id} (value 0.57)...")
    del_success = await client.delete_datapoint(goal_slug, old_id)
    print(f"Result: {'SUCCESS' if del_success else 'FAILED'}")
    
    # Add the correct 0.87 datapoint on May 31st
    print("\nAdding correct May 31st datapoint (value 0.87: $0.37 + $0.50)...")
    add_success = await client.add_datapoint(
        goal_slug=goal_slug,
        value=0.87,
        comment="Final value for May: $0.37 (account spend) + $0.50 (API spend)",
        daystamp="20260531"
    )
    print(f"Result: {'SUCCESS' if add_success else 'FAILED'}")
    
    # Fetch and verify history
    print("\nFetching updated history to verify...")
    datapoints = await client.get_goal_datapoints(goal_slug, count=10)
    for dp in datapoints:
        print(f"ID: {dp.get('id')}, Date: {dp.get('daystamp')}, Value: {dp.get('value')}, Comment: {dp.get('comment')}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
