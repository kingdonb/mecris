from typing import List, Dict, Any, Optional

def prune_history(messages: List[Dict[str, Any]], max_messages: int = 20) -> List[Dict[str, Any]]:
    """
    Prune history to keep the system prompt and the last N messages.
    """
    if len(messages) <= max_messages:
        return messages

    system_messages = [m for m in messages if m.get("role") == "system"]
    other_messages = [m for m in messages if m.get("role") != "system"]
    
    # Keep the last (max_messages - len(system_messages)) messages
    keep_count = max(0, max_messages - len(system_messages))
    return system_messages + other_messages[-keep_count:]

class MecrisHarness:
    def __init__(self, llm_client: Any, mcp_client: Any):
        self.llm_client = llm_client
        self.mcp_client = mcp_client

    async def run_loop(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> str:
        while True:
            response = await self.llm_client.chat(model="gemma4:12b", messages=messages, tools=tools)
            
            # Ollama returns dict, not object attributes. The mock needs to match this.
            msg = response.get("message", {})
            
            messages.append({
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": msg.get("tool_calls")
            })

            # Check for tool calls
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tool_call in tool_calls:
                    name = tool_call["function"]["name"]
                    args = tool_call["function"]["arguments"]
                    result = await self.mcp_client.call_tool(name, args)
                    messages.append({
                        "role": "tool",
                        "name": name,
                        "content": str(result)
                    })
                continue
            
            return msg.get("content", "")
