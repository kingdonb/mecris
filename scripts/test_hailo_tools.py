import httpx
import json
import asyncio

async def test_tools_as_string():
    url = "http://192.168.2.109:30800/api/chat"
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather in Paris"
            }
        }
    ]
    payload = {
        "model": "qwen2:1.5b",
        "messages": [
            {"role": "user", "content": "What is the weather like in Paris?"}
        ],
        "tools": json.dumps(tools),
        "stream": False
    }
    print("Testing chat response with tools parameter as serialized string...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=15.0)
            print("Status Code:", resp.status_code)
            print("Response:", resp.text)
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test_tools_as_string())
