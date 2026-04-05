
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
    to_delete = [dp for dp in datapoints if dp.get('daystamp') == '20260404']
    
    print(f"Found {len(to_delete)} datapoints to delete for today.")
    
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

    # 2. Push the CORRECT total for today
    # Today's max distance was 981.0058 meters
    today_total_miles = 981.005822397284 / 1609.34
    print(f"Correct today's total: {today_total_miles:.3f} miles")
    
    # We use a day-level requestid to ensure idempotency for "total for today" source
    daystamp = "20260404"
    request_id = f"{user_id}_{daystamp}"
    
    comment = f"Mecris Corrected Sync: Total for {daystamp} (Steps: 3200)"
    
    success = await client.add_datapoint(goal_slug, today_total_miles, comment=comment, requestid=request_id)
    if success:
        print(f"Successfully pushed correct consolidated datapoint with requestid: {request_id}")
    else:
        print("Failed to push correct consolidated datapoint.")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
