import httpx
import json
import asyncio

async def main():
    url = "http://192.168.2.109:30434/api/chat"
    
    system_prompt = (
        "You are Mecris, a personal accountability robot. You have access to these tools:\n"
        "- get_narrator_context: Get the current status of all goals and budget.\n\n"
        "If you need to call a tool, respond ONLY with a JSON object in this format:\n"
        '{"tool": "get_narrator_context", "arguments": {}}\n'
        "Otherwise, respond with your normal message to the user."
    )
    
    payload = {
        "model": "qwen2:1.5b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Mecris, check my goals status."}
        ],
        "stream": False
    }
    
    print("Testing prompt-based tool calling with Qwen2 1.5B on Hailo...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=20.0)
            print("Status Code:", resp.status_code)
            res_json = resp.json()
            print("Response content:")
            print(res_json.get("message", {}).get("content"))
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
