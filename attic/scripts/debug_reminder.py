import asyncio
from dotenv import load_dotenv
from mcp_server import trigger_reminder_check

load_dotenv()

async def main():
    print("Testing reminder logic...")
    result = await trigger_reminder_check()
    print("Result:", result)

asyncio.run(main())
