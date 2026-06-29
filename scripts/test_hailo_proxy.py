import httpx
import json
import asyncio

async def main():
    ip = "192.168.2.109"
    port = 30434  # Proxy port
    
    # 1. Define a tool
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather in a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    # 2. Chat with tools
    url_chat = f"http://{ip}:{port}/api/chat"
    payload = {
        "model": "qwen2:1.5b",
        "messages": [
            {"role": "user", "content": "What is the weather like in Paris?"}
        ],
        "tools": tools,
        "stream": False
    }
    print(f"Testing chat with tools via proxy {url_chat}...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url_chat, json=payload, timeout=20.0)
            print("Proxy Chat Response Status:", resp.status_code)
            print("Response body:")
            print(resp.text)
        except Exception as e:
            print("Failed chat:", e)

if __name__ == "__main__":
    asyncio.run(main())
