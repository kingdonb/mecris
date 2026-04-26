import asyncio
import os
from beeminder_client import BeeminderClient

async def main():
    client = BeeminderClient(user_id="yebyen")
    success = await client.add_datapoint(
        "groqspend", 
        0.28, 
        "Logged via Gemini CLI: Beta 4 Testing Session (vcluster setup)"
    )
    print(f"Success: {success}")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
