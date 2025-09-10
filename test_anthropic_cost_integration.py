#!/usr/bin/env python3
"""
Test script to demonstrate Anthropic Cost & Usage API integration

This shows how the integration works and what errors you get without 
organization access.
"""

import os
import sys
import json
from datetime import datetime

def test_anthropic_cost_tracker():
    """Test the Anthropic Cost Tracker integration"""
    print("🔍 Testing Anthropic Cost & Usage API Integration")
    print("=" * 60)
    
    # Check if real admin key is available
    admin_key = os.environ.get('ANTHROPIC_ADMIN_KEY')
    if admin_key:
        print(f"\n1️⃣ Testing with real ANTHROPIC_ADMIN_KEY")
        print("   ✅ Admin key found in environment")
        
        try:
            from scripts.anthropic_cost_tracker import AnthropicCostTracker
            tracker = AnthropicCostTracker()
            print("   ✅ Tracker initialized with real admin key")
            
            # Try to get budget summary
            print("   📡 Attempting API call to get budget summary...")
            summary = tracker.get_budget_summary()
            print(f"   🎉 SUCCESS: {summary}")
            
        except Exception as e:
            print(f"   ⚠️ API error: {e}")
            print("   → Check if admin key has correct permissions")
    else:
        print("\n1️⃣ Testing without ANTHROPIC_ADMIN_KEY")
        try:
            from scripts.anthropic_cost_tracker import AnthropicCostTracker
            tracker = AnthropicCostTracker()
            print("   ❌ This shouldn't happen - no admin key provided")
        except ValueError as e:
            print(f"   ✅ Expected error: {e}")
            print("   → Add ANTHROPIC_ADMIN_KEY to .env to test real API")
    
    # Test 2: MCP Server Integration
    print("\n2️⃣ Testing MCP Server Integration")
    try:
        import mcp_server
        print("   ✅ MCP server imports successfully")
        
        # Check if the anthropic tracker is available
        if hasattr(mcp_server, 'anthropic_cost_tracker') and mcp_server.anthropic_cost_tracker:
            print("   ✅ anthropic_cost_tracker initialized")
        else:
            print("   ⚠️ anthropic_cost_tracker not available (check admin key)")
            
    except Exception as e:
        print(f"   ❌ MCP server integration error: {e}")
    
    # Test 3: Current Fallback System
    print("\n3️⃣ Current System (Local Usage Tracking)")
    try:
        from usage_tracker import get_budget_status
        budget = get_budget_status()
        print("   ✅ Local usage tracking works:")
        print(f"   • Days remaining: {budget.get('days_remaining', 'N/A')}")
        print(f"   • Remaining budget: ${budget.get('remaining_budget', 0):.2f}")
        print("   → This is your current working system")
    except Exception as e:
        print(f"   ❌ Local usage tracking error: {e}")
    
    # Test 4: API Integration Status
    print("\n4️⃣ API Integration Status")
    if admin_key:
        print("   ✅ Admin key configured - API integration ready")
        print("   📋 API Endpoints available:")
        print("   • GET /v1/usage-cost/get-messages-usage-report")
        print("   • GET /v1/usage-cost/get-cost-report") 
        print("   • Headers: x-api-key + anthropic-version: 2023-06-01")
    else:
        print("   ⚠️ No admin key - using local tracking only")
        print("   📋 To enable API integration:")
        print("   • Add ANTHROPIC_ADMIN_KEY to .env")
        print("   • Get admin key from Console → Settings → Organization")

if __name__ == "__main__":
    test_anthropic_cost_tracker()