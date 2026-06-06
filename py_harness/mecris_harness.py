from typing import List, Dict, Any, Optional

class MecrisHarness:
    def __init__(self, llm_client: Any, mcp_client: Any):
        self.llm_client = llm_client
        self.mcp_client = mcp_client

    async def run_loop(self, messages: List[Dict[str, Any]]) -> str:
        while True:
            response = await self.llm_client.chat(messages=messages)
            
            # Add assistant message to history
            messages.append({
                "role": "assistant",
                "content": response.message.content,
                "tool_calls": getattr(response.message, "tool_calls", None)
            })

            if response.stop_reason == "tool_use":
                for tool_call in response.message.tool_calls:
                    name = tool_call.function.name
                    args = tool_call.function.arguments
                    result = await self.mcp_client.call_tool(name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": getattr(tool_call, "id", "mock_id"),
                        "name": name,
                        "content": result
                    })
                continue
            
            return response.message.content or ""
