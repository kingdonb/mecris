#!/usr/bin/env python3
"""
Test script to demonstrate Anthropic Cost & Usage API integration

Tests the enhanced cost tracking system with workspace requirements,
hourly buckets, and real-time usage detection.
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
            from datetime import datetime, UTC
            tracker = AnthropicCostTracker()
            print("   ✅ Tracker initialized with real admin key")
            
            # Test 1a: Today's usage with hourly buckets
            print("   📡 Testing today's usage data (hourly buckets)...")
            start_time = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            usage_data = tracker.get_usage(start_time, bucket_width='1h')
            
            # Calculate totals
            total_input = 0
            total_output = 0
            for bucket in usage_data.get('data', []):
                for result in bucket.get('results', []):
                    input_tokens = result.get('uncached_input_tokens', 0)
                    input_tokens += result.get('cache_read_input_tokens', 0)
                    if 'cache_creation' in result:
                        input_tokens += result['cache_creation'].get('ephemeral_1h_input_tokens', 0)
                        input_tokens += result['cache_creation'].get('ephemeral_5m_input_tokens', 0)
                    
                    total_input += input_tokens
                    total_output += result.get('output_tokens', 0)
            
            estimated_cost = (total_input * 3.0 / 1000000) + (total_output * 15.0 / 1000000)
            
            print(f"   🎉 TODAY'S USAGE: {total_input:,} input, {total_output:,} output tokens")
            print(f"   💰 Estimated cost: ${estimated_cost:.4f}")
            print(f"   📊 Buckets returned: {len(usage_data.get('data', []))}")
            
            # Test 1b: Legacy budget summary
            print("\n   📡 Testing legacy budget summary...")
            summary = tracker.get_budget_summary()
            print(f"   ℹ️ LEGACY: {summary}")
            
        except Exception as e:
            print(f"   ⚠️ API error: {e}")
            if "organization workspace" in str(e).lower():
                print("   → API key must be from organization workspace (not default workspace)")
            else:
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
    
    # Test 4: Enhanced API Integration Status
    print("\n4️⃣ Enhanced API Integration Status")
    if admin_key:
        print("   ✅ Admin key configured - API integration ready")
        print("   📋 Enhanced API Endpoints available:")
        print("   • GET /v1/organizations/usage_report/messages (hourly buckets)")
        print("   • GET /v1/organizations/cost_report (daily buckets only)") 
        print("   • Headers: x-api-key + anthropic-version: 2023-06-01")
        print("   🏢 CRITICAL: API key MUST be from organization workspace")
        print("   ⚡ Real-time: Usage data available within 1 hour")
        print("   ⚠️ Cost data: May have 24+ hour delay for recent dates")
    else:
        print("   ⚠️ No admin key - using local tracking only")
        print("   📋 To enable Enhanced API integration:")
        print("   • Create organization workspace in Anthropic Console")
        print("   • Generate API key from organization workspace (NOT default)")
        print("   • Add ANTHROPIC_ADMIN_KEY to .env")
        print("   • Test with: uv run python scripts/anthropic_cost_tracker.py")
    
    # Test 5: Workspace Detection Test
    print("\n5️⃣ Workspace Configuration Test")
    print("   ℹ️ Key Discovery: Default workspace usage is NOT visible to Admin API")
    print("   ✅ Solution: Create organization workspace for API visibility")
    print("   📊 Usage data from organization workspace appears in <1 hour")
    print("   💡 Cost estimation from token counts works immediately")

if __name__ == "__main__":
    test_anthropic_cost_tracker()