import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to python path to load local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beeminder_client import BeeminderClient

async def main():
    load_dotenv()
    
    # Use the familiar user ID mapped from local configuration
    client = BeeminderClient(user_id="c0a81a4b-115a-4eb6-bc2c-40908c58bf64")
    goal_slug = "groqspend"
    
    print("=== STARTING BEEMINDER AUDIT & CLEANUP FOR GROQSPEND ===")
    
    # 1. Delete bad backdated datapoints
    bad_datapoints = [
        {"id": "6a43bda3d4865fd5eb2939be", "desc": "0.86 June final backdated to 20260531"},
        {"id": "6a2a1890d4865fb51835d9d3", "desc": "0.35 June mid-month backdated to 20260531"},
        {"id": "6a2a1890d4865fb50435dc6d", "desc": "0.20 May spend backdated to 20260430"}
    ]
    
    for dp in bad_datapoints:
        print(f"Deleting datapoint {dp['id']} ({dp['desc']})...")
        success = await client.delete_datapoint(goal_slug, dp['id'])
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        
    # 2. Add June final spend on the correct daystamp (20260630)
    print("\nRecording June final spend on the correct date (20260630)...")
    success = await client.add_datapoint(
        goal_slug=goal_slug,
        value=0.86,
        comment="Month-end reading: $0.50 (account spend) + $0.36 (API spend)",
        daystamp="20260630"
    )
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
    
    # 3. Retrieve final history to produce audit report
    print("\nFetching updated datapoints for final audit...")
    datapoints = await client.get_goal_datapoints(goal_slug, count=40)
    
    # Organize data by month
    monthly_data = {}
    for dp in datapoints:
        daystamp = dp.get("daystamp")
        if not daystamp or len(daystamp) != 8:
            continue
        year = daystamp[0:4]
        month = daystamp[4:6]
        day = daystamp[6:8]
        month_key = f"{year}-{month}"
        
        if month_key not in monthly_data:
            monthly_data[month_key] = []
        monthly_data[month_key].append({
            "day": day,
            "value": float(dp.get("value", 0.0)),
            "comment": dp.get("comment", "")
        })
        
    print("\n=== GROQSPEND AUDIT REPORT ===")
    print(f"{'Month':<10} | {'Days Traced':<12} | {'Max Spend':<10} | {'Status':<15}")
    print("-" * 57)
    
    for month_key in sorted(monthly_data.keys(), reverse=True):
        readings = monthly_data[month_key]
        if not readings:
            continue
        max_spend = max(r["value"] for r in readings)
        days_traced = len(set(r["day"] for r in readings))
        status = "PASSED (< $1.00)" if max_spend < 1.00 else "EXCEEDED LIMIT"
        print(f"{month_key:<10} | {days_traced:<12} | ${max_spend:<9.2f} | {status:<15}")
        
    print("\nDetailed Datapoints:")
    for month_key in sorted(monthly_data.keys(), reverse=True):
        print(f"\nMonth: {month_key}")
        for r in sorted(monthly_data[month_key], key=lambda x: x["day"]):
            print(f"  Day {r['day']}: ${r['value']:.2f} - {r['comment']}")
            
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
