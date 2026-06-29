import asyncio
import os
import sys
from py_harness.mcp_client import MecrisMcpClient, filter_core_tools
from py_harness.ollama_client import OllamaClient
from py_harness.mecris_harness import MecrisHarness

async def run_test():
    ollama_host = os.environ.get("OLLAMA_HOST", "http://192.168.2.109:30434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2:1.5b")
    use_native = os.environ.get("OLLAMA_NATIVE_TOOLS", "false").lower() == "true"

    print("=== Mecris Prompt-Based ReAct test ===")
    print(f"Config: host={ollama_host}, model={ollama_model}, native_tools={use_native}")

    async with MecrisMcpClient() as mcp_client:
        tools_response = await mcp_client.list_tools()
        core_tools = filter_core_tools([t.model_dump() if hasattr(t, "model_dump") else vars(t) for t in tools_response.tools])
        print(f"Loaded {len(core_tools)} core tools.")
        
        ollama_tools = [{"type": "function", "function": t} for t in core_tools]
        ollama_client = OllamaClient(ollama_host, use_native_tools=use_native)
        ollama_client.model = ollama_model
        
        messages = [
            {"role": "system", "content": "You are Mecris, a personal accountability robot. Talk like caveman (terse, no articles, no filler). Brain big, mouth small. Before answering the user, you must call get_narrator_context to check their status."}
        ]
        
        harness = MecrisHarness(ollama_client, mcp_client)
        
        user_input = "Mecris, what is my status?"
        print(f"\nUser: {user_input}")
        messages.append({"role": "user", "content": user_input})
        
        response_content = await harness.run_loop(messages, tools=ollama_tools)
        print(f"\nMecris final response: {response_content}")

if __name__ == "__main__":
    asyncio.run(run_test())
