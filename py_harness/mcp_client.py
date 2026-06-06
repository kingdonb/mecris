import asyncio
import sys
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MecrisMcpClient:
    def __init__(self, server_script: str = "mcp_server.py"):
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=None
        )
        self.session = None
        self._exit_stack = None

    async def __aenter__(self):
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(self.server_params))
        self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._exit_stack:
            await self._exit_stack.aclose()

    async def list_tools(self):
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context.")
        return await self.session.list_tools()

    async def call_tool(self, name: str, arguments: dict):
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context.")
        return await self.session.call_tool(name, arguments)
