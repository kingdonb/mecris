#!/usr/bin/env python3
import os
import json
import time
import httpx
from datetime import datetime, timezone

# Helix Configuration
HELIX_API_KEY = "REDACTED_HELIX_API_KEY"
HELIX_BASE_URL = "https://app.helix.ml/v1"
RESULTS_FILE = "experiments/helix_benchmark/results.jsonl"

# Models to test
MODELS = [
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-haiku-20240307",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "Qwen/Qwen3-8B" # Already know this works
]

PROMPT = "Summarize the key value proposition of WASM for developers in 3 short bullet points."

def run_benchmark(model_id):
    print(f"--- Testing Model: {model_id} ---")
    start_time = time.time()
    
    headers = {
        "Authorization": f"Bearer {HELIX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 300,
        "temperature": 0.5
    }
    
    try:
        # Long timeout for VLLM cold starts
        with httpx.Client(timeout=180.0) as client:
            response = client.post(f"{HELIX_BASE_URL}/chat/completions", json=payload, headers=headers)
            
        latency = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model_id,
                "latency_sec": round(latency, 2),
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "content": content,
                "status": "success"
            }
            print(f"✅ Success ({latency:.2f}s)")
            return result
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model_id,
                "status": "error",
                "error_code": response.status_code,
                "error_msg": response.text
            }
            
    except Exception as e:
        print(f"⚠️ Exception: {str(e)}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model_id,
            "status": "exception",
            "error": str(e)
        }

def main():
    if not os.path.exists(os.path.dirname(RESULTS_FILE)):
        os.makedirs(os.path.dirname(RESULTS_FILE))
        
    for model in MODELS:
        result = run_benchmark(model)
        with open(RESULTS_FILE, "a") as f:
            f.write(json.dumps(result) + "\n")
        time.sleep(1)

if __name__ == "__main__":
    main()
