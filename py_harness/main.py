import asyncio
import sys
import os
from py_harness.mcp_client import MecrisMcpClient, filter_core_tools
from py_harness.ollama_client import OllamaClient
from py_harness.mecris_harness import MecrisHarness, prune_history

async def main():
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4:12b")
    use_native = os.environ.get("OLLAMA_NATIVE_TOOLS", "true").lower() == "true"
    
    print("Starting local Mecris MCP harness (Python)...")
    print(f"Config: host={ollama_host}, model={ollama_model}, native_tools={use_native}")
    
    async with MecrisMcpClient() as mcp_client:
        tools_response = await mcp_client.list_tools()
        # tools_response is a ListToolsResult object
        core_tools = filter_core_tools([t.model_dump() if hasattr(t, "model_dump") else vars(t) for t in tools_response.tools])
        print(f"Loaded {len(core_tools)} core tools.")
        
        # Convert tools to Ollama format
        ollama_tools = [{"type": "function", "function": t} for t in core_tools]
        
        ollama_client = OllamaClient(ollama_host, use_native_tools=use_native)
        ollama_client.model = ollama_model
        
        # We need a modified run_loop that takes tools since Ollama needs them.
        # But for now, we'll just handle the top-level loop here.
        
        messages = [
            {"role": "system", "content": "You are Mecris, a personal accountability robot. Talk like caveman (terse, no articles, no filler). Brain big, mouth small. Before answering the user, you must call get_narrator_context to check their status."}
        ]
        
        # Initialize harness
        # We'll pass the ollama format tools directly inside run_loop or here
        harness = MecrisHarness(ollama_client, mcp_client)
        
        print("Mecris Harness Started. Type 'exit' to quit.")
        
        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
                
            if user_input.lower() in ("exit", "quit"):
                break
                
            messages.append({"role": "user", "content": user_input})
            messages = prune_history(messages)
            
            # The run_loop handles the ReAct logic and returns when the assistant has a message for the user.
            response_content = await harness.run_loop(messages, tools=ollama_tools)
            print(f"\nMecris: {response_content}")

if __name__ == "__main__":
    asyncio.run(main())
