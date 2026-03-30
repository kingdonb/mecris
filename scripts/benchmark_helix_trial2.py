#!/usr/bin/env python3
import os
import json
import time
import httpx
from datetime import datetime, timezone

# Helix Configuration
HELIX_API_KEY = "REDACTED_HELIX_API_KEY"
HELIX_BASE_URL = "https://app.helix.ml/v1"
RESULTS_FILE = "experiments/helix_benchmark/trial_2_results.jsonl"

# The "Brain Migration" Task
PROMPT = """You are a senior systems architect. 
We are migrating our 'Accountability Brain' from a Python monolithic MCP server into discrete WebAssembly (WASM) components hosted by Spin (a serverless WebAssembly framework).
Our first component is 'ReviewPump', a pure mathematical function that calculates daily flashcard review targets based on current debt and a multiplier lever.

Write a technical manifesto (approx 300 words) justifying this 'Logic Vacuuming' migration. 
Focus on:
1. The resilience of the system (the brain survives if the Python server crashes).
2. The deterministic, secure sandbox that WASM provides for core logic.
3. The future-proofing of our architecture to eventually run this logic directly on an Android device using Wasmtime.

Adopt a professional, slightly visionary tone."""

# Models to test: The Native "Free" Tier vs The Proxied Tier
MODELS = [
    # ---------------------------------------------------------
    # Tier 1: The Native "Free" GPU Fleet (VLLM on Helix Infra)
    # ---------------------------------------------------------
    "Qwen/Qwen3-8B",
    "Qwen/Qwen2.5-VL-7B-Instruct",
    "Qwen/Qwen2.5-VL-3B-Instruct",
    
    # ---------------------------------------------------------
    # Tier 2: The Proxied API Fleet (Consumes $100 Credit)
    # ---------------------------------------------------------
    "anthropic/claude-3-haiku-20240307",
    "anthropic/claude-3-5-sonnet-20241022",  # Still trying to find the exact slug
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4o-mini"
]

def run_benchmark(model_id):
    print(f"\n--- Testing Model: {model_id} ---")
    start_time = time.time()
    
    headers = {
        "Authorization": f"Bearer {HELIX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 800,
        "temperature": 0.7
    }
    
    try:
        # Long timeout for VLLM cold starts on native hardware
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
            print(f"✅ Success ({latency:.2f}s) - {usage.get('completion_tokens')} tokens generated.")
            return result
        else:
            print(f"❌ Failed: {response.status_code} - {response.text[:150]}")
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
        time.sleep(2)

if __name__ == "__main__":
    main()
