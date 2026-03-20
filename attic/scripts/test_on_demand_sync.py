import asyncio
from mcp_server import mcp

async def main():
    print("Available tools:", [t.name for t in mcp.tools])

asyncio.run(main())
