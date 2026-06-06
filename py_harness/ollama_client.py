import httpx
from typing import List, Dict, Any

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def chat(self, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=60.0)
            response.raise_for_status()
            return response.json()
