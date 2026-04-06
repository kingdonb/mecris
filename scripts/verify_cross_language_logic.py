"""
Mecris DMZ: Cross-Language Logic Verifier

This script exercises both Python and Rust WASM components with identical inputs
to ensure logic parity and detect architectural drift.

Usage:
    python scripts/verify_cross_language_logic.py --url http://localhost:3000
"""

import requests
import json
import argparse
import sys

def verify_review_pump(base_url):
    print("--- Verifying Review Pump (PY vs RS) ---")
    payload = {
        "debt": 140,
        "tomorrow_liability": 50,
        "daily_completions": 60,
        "multiplier_x10": 20, # Steady (14 days)
        "unit": "points"
    }
    
    # Python endpoint
    py_resp = requests.post(f"{base_url}/internal/review-pump-status-py", json=payload)
    # Rust endpoint
    rs_resp = requests.post(f"{base_url}/internal/review-pump-status-rs", json=payload)
    
    if py_resp.status_code != 200 or rs_resp.status_code != 200:
        print(f"FAILED: Status mismatch (PY: {py_resp.status_code}, RS: {rs_resp.status_code})")
        return False
        
    py_data = py_resp.json()
    rs_data = rs_resp.json()
    
    # We ignore the key names if they slightly differ but check the values
    # PY: goal_met, target_flow_rate, status
    # RS: goal_met, target_flow_rate, status
    
    match = True
    for key in ["goal_met", "target_flow_rate", "status", "debt_remaining"]:
        if py_data.get(key) != rs_data.get(key):
            print(f"DIVERGENCE in {key}: PY={py_data.get(key)}, RS={rs_data.get(key)}")
            match = False
            
    if match:
        print("✅ Review Pump Parity Achieved.")
    return match

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3000")
    args = parser.parse_args()
    
    success = True
    if not verify_review_pump(args.url):
        success = False
        
    if not success:
        print("\n❌ HARMONY BROKEN: Logic divergence detected.")
        sys.exit(1)
    else:
        print("\n✨ HARMONY RESTORED: Python and Rust are in agreement.")

if __name__ == "__main__":
    main()
