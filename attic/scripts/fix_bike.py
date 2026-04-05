
import asyncio
import os
import httpx
from datetime import datetime
import zoneinfo
from beeminder_client import BeeminderClient

async def main():
    user_id = 'c0a81a4b-115a-4eb6-bc2c-40908c58bf64'
    client = BeeminderClient(user_id=user_id)
    await client._load_credentials()
    
    username = client.username
    auth_token = client.auth_token
    goal_slug = 'bike'
    
    # 1. Identify today's datapoints to delete
    eastern = zoneinfo.ZoneInfo('US/Eastern')
    now_eastern = datetime.now(eastern)
    today_start = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    
    datapoints = await client.get_goal_datapoints(goal_slug, since=today_start, count=50)
    # Filter for today's daystamp 20260404
    to_delete = [dp for dp in datapoints if dp.get('daystamp') == '20260404']
    
    print(f"Found {len(to_delete)} datapoints to delete for today.")
    
    # 2. Delete them
    async with httpx.AsyncClient() as http:
        for dp in to_delete:
            dp_id = dp['id']
            url = f"https://www.beeminder.com/api/v1/users/{username}/goals/{goal_slug}/datapoints/{dp_id}.json"
            print(f"Deleting datapoint {dp_id} (value: {dp['value']})...")
            resp = await http.delete(url, params={'auth_token': auth_token})
            if resp.status_code == 200:
                print(f"Successfully deleted {dp_id}.")
            else:
                print(f"Failed to delete {dp_id}: {resp.status_code} {resp.text}")

    # 3. Calculate today's total miles
    # We found 25 walks earlier. Let's sum their distances.
    # Note: Values from 'check_bike.py' for today (April 4):
    # 0.987, 1.134, 0.012, 0.128, 1.298, 0.332, 1.213, 1.025, 0.927, 1.276, 
    # 1.407, 1.121, 0.184, 0.910, 0.216, 0.023, 0.165, 0.165, 0.195, 0.0, 
    # 0.198, 1.099, 1.639, 0.001, 0.609
    
    # Total distance today according to our sync records
    total_today_miles = sum(float(dp['value']) for dp in to_delete)
    print(f"Total miles today: {total_today_miles:.3f}")
    
    # 4. Get last known total from yesterday
    # From get_beeminder_status earlier: current_value was 1060.1353871053577
    # (This was before my messed up sync)
    previous_total = 1060.1353871053577
    
    new_total = previous_total + total_today_miles
    print(f"New cumulative total: {new_total:.3f}")
    
    # 5. Push ONE datapoint
    comment = f"Mecris Sync Correction: Consolidated {len(to_delete)} walks for today."
    success = await client.add_datapoint(goal_slug, new_total, comment=comment)
    if success:
        print("Successfully pushed consolidated datapoint.")
    else:
        print("Failed to push consolidated datapoint.")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
