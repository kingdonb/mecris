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
            # Observability: Show what we are sending to the model
            # print(f"[debug] Sending {len(messages)} messages to Ollama...")
            
            response = await self.llm_client.chat(model="gemma4:12b", messages=messages, tools=tools)
            
            msg = response.get("message", {})
            
            # Observability: Show thinking/content
            if msg.get("content"):
                pass # Already handled by main loop print, but we could log it here too

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
                    
                    print(f"⛏️  Caveman use tool: {name}")
                    result = await self.mcp_client.call_tool(name, args)
                    
                    # result is a CallToolResult
                    content = ""
                    if hasattr(result, "content"):
                        content = "\n".join([c.text for c in result.content if hasattr(c, "text")])
                    
                    print(f"✅ Tool result size: {len(content)} chars")
                    
                    messages.append({
                        "role": "tool",
                        "name": name,
                        "content": content
                    })
                continue
            
            return msg.get("content", "")
