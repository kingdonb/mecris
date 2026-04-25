import asyncio
import os
import sys

from mcp_server import get_user_beeminder_client

async def main():
    try:
        user_id = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
        client = get_user_beeminder_client(user_id)
        await client.add_datapoint("groqspend", 0.21, comment="Caught up with 21 cents")
        print("Success")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
