import httpx
from typing import List, Dict, Any

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", use_native_tools: bool = True):
        self.base_url = base_url
        self.use_native_tools = use_native_tools

    async def chat(self, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        # Extract system prompt for Ollama/Hailo-Ollama top-level compatibility
        system_content = None
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content")
                break
        if system_content:
            payload["system"] = system_content

        if tools and self.use_native_tools:
            payload["tools"] = tools

        async with httpx.AsyncClient() as client:
            # Local inference (especially with tools) can be slow. 5m timeout.
            response = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=300.0)
            response.raise_for_status()
            return response.json()
