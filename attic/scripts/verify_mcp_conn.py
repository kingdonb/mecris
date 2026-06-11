import asyncio
from py_harness.mcp_client import MecrisMcpClient

async def test_real_mcp():
    async with MecrisMcpClient() as client:
        tools = await client.list_tools()
        print(f"Found {len(tools.tools)} tools")
        for tool in tools.tools[:3]:
            print(f"- {tool.name}")

if __name__ == "__main__":
    asyncio.run(test_real_mcp())
