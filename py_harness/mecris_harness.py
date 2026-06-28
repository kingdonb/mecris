import json
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

    def _inject_tools_description(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        # Find the system message
        sys_msg = None
        for m in messages:
            if m.get("role") == "system":
                sys_msg = m
                break
        
        if not sys_msg:
            sys_msg = {"role": "system", "content": ""}
            messages.insert(0, sys_msg)
            
        # Format the tools description
        tools_desc = "\n\nYou have access to the following tools:\n"
        for t in tools:
            func = t.get("function", t)
            name = func.get("name")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            tools_desc += f"- {name}: {desc}. Parameters: {json.dumps(params)}\n"
            
        tools_desc += (
            "\nCRITICAL: If you need to use a tool to get information, you MUST respond ONLY with a JSON object matching this schema:\n"
            '{"tool": "tool_name", "arguments": {...}}\n'
            "Do not include any other conversational text or markdown code fences outside the JSON object.\n"
            "Once you receive the tool result, proceed to answer the user."
        )
        
        # Avoid duplicate injections
        if "[Tool Description]" not in sys_msg["content"]:
            sys_msg["content"] += f"\n\n[Tool Description]\n{tools_desc}"

    async def run_loop(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> str:
        # If native tools are disabled, inject them into the system prompt text
        use_native = getattr(self.llm_client, "use_native_tools", True)
        if not use_native and tools:
            self._inject_tools_description(messages, tools)

        # We keep track of the model to use from the client, default to gemma4:12b
        model = getattr(self.llm_client, "model", "gemma4:12b")

        while True:
            try:
                response = await self.llm_client.chat(model=model, messages=messages, tools=tools)
            except Exception as e:
                return f"Mecris brain stall: {str(e)}. Try again?"
            
            msg = response.get("message", {})
            content_text = msg.get("content") or ""

            # Check for tool calls
            tool_calls = msg.get("tool_calls")
            
            # Fallback: Parse prompt-based tool calls if native tools are disabled
            if not tool_calls and not use_native and content_text:
                cleaned = content_text.strip()
                # Strip markdown code fences if outputted
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    if len(lines) >= 2 and (lines[0].startswith("```json") or lines[0].startswith("```")):
                        if lines[-1].strip() == "```":
                            cleaned = "\n".join(lines[1:-1]).strip()
                        else:
                            cleaned = "\n".join(lines[1:]).strip()
                
                # 1. Try substring JSON extraction (handles mixed text + JSON outputs)
                for start_idx in range(len(cleaned)):
                    if cleaned[start_idx] == "{":
                        for end_idx in range(len(cleaned), start_idx, -1):
                            substr = cleaned[start_idx:end_idx]
                            try:
                                parsed = json.loads(substr)
                                if isinstance(parsed, dict):
                                    name = parsed.get("tool") or parsed.get("name")
                                    args = parsed.get("arguments", {})
                                    if name:
                                        tool_calls = [{
                                            "function": {
                                                "name": name,
                                                "arguments": args
                                            }
                                        }]
                                        break
                            except json.JSONDecodeError:
                                pass
                        if tool_calls:
                            break

                # 2. If JSON extraction didn't work, perform case-insensitive check for textual calls like [get_narrator_context] or just Get_narrator_context
                if not tool_calls and tools:
                    import re
                    content_lower = content_text.lower()
                    for t in tools:
                        func = t.get("function", t)
                        orig_name = func.get("name")
                        name_lower = orig_name.lower()
                        patterns = [
                            rf"\[{re.escape(name_lower)}\]",  # [tool_name]
                            rf"\[{re.escape(name_lower)}\((.*?)\)\]",  # [tool_name(args)]
                            rf"{re.escape(name_lower)}\((.*?)\)",  # tool_name(args)
                            rf"\b{re.escape(name_lower)}\b",  # tool_name as standalone word
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, content_lower)
                            if match:
                                args = {}
                                # Extract arguments if there is a capture group
                                if len(match.groups()) > 0 and match.group(1):
                                    try:
                                        # Use indices from original case-sensitive text to extract arguments if JSON
                                        raw_args = content_text[match.start(1):match.end(1)].strip()
                                        args = json.loads(raw_args)
                                    except Exception:
                                        pass
                                tool_calls = [{
                                    "function": {
                                        "name": orig_name,
                                        "arguments": args
                                    }
                                }]
                                break
                        if tool_calls:
                            break

            messages.append({
                "role": "assistant",
                "content": content_text,
                "tool_calls": tool_calls
            })

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
                    
                    # Defensively prune get_narrator_context output for edge models to avoid NPU cache saturation
                    if not use_native and name == "get_narrator_context":
                        try:
                            data = json.loads(content)
                            pruned_data = {
                                "summary": data.get("summary"),
                                "urgent_items": data.get("urgent_items"),
                                "goal_runway": data.get("goal_runway"),
                                "recommendations": data.get("recommendations"),
                                "budget_status": data.get("budget_status"),
                            }
                            content = json.dumps(pruned_data, ensure_ascii=False, indent=2)
                            print(f"✂️  Pruned tool result to: {len(content)} chars")
                        except Exception:
                            pass
                    
                    # If prompt-based, pass result back as a user message format to ensure model compatibility
                    role = "tool" if use_native else "user"
                    final_content = content if use_native else f"[Tool Output: {name}]\n{content}"
                    
                    messages.append({
                        "role": role,
                        "name": name,
                        "content": final_content
                    })
                continue
            
            return content_text
