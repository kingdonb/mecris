import os
import asyncio
import json
import sys
from dotenv import load_dotenv

# Ensure we can import from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_server import get_narrator_context
from services.credentials_manager import credentials_manager

load_dotenv()

async def main():
    user_id = credentials_manager.resolve_user_id(None)
    print(f"Calling get_narrator_context for user: {user_id}")
    try:
        context = await get_narrator_context(user_id)
        print(json.dumps(context, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
