#!/usr/bin/env python3
"""
Simple Narrator Context Test
Direct test of narrator context functionality without complex async unittest setup
"""

import asyncio
import httpx
import json
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_narrator_context_basic():
    """Basic test of narrator context endpoint"""
    server_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print("🔍 Testing narrator context endpoint...")
            response = await client.get(f"{server_url}/narrator/context")
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            # Check required fields
            required_fields = [
                "summary", "goals_status", "urgent_items", 
                "beeminder_alerts", "goal_runway", "budget_status",
                "recommendations", "last_updated"
            ]
            
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
            
            # Check data types
            type_checks = [
                ("summary", str),
                ("goals_status", dict),
                ("urgent_items", list),
                ("beeminder_alerts", list),
                ("goal_runway", list),
                ("budget_status", dict),
                ("recommendations", list)
            ]
            
            for field, expected_type in type_checks:
                if not isinstance(data[field], expected_type):
                    print(f"❌ Field '{field}' should be {expected_type.__name__}, got {type(data[field]).__name__}")
                    return False
            
            print(f"✅ Narrator context structure valid")
            print(f"   Summary: {data['summary'][:50]}...")
            print(f"   Urgent items: {len(data['urgent_items'])}")
            print(f"   Recommendations: {len(data['recommendations'])}")
            print(f"   Budget days remaining: {data['budget_status'].get('days_remaining', 'unknown')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False


async def test_narrator_context_performance():
    """Test narrator context performance"""
    server_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print("⏱️  Testing narrator context performance...")
            
            import time
            
            # First request
            start_time = time.time()
            response1 = await client.get(f"{server_url}/narrator/context")
            first_time = time.time() - start_time
            
            # Second request (should benefit from caching)
            start_time = time.time()
            response2 = await client.get(f"{server_url}/narrator/context")
            second_time = time.time() - start_time
            
            if response1.status_code != 200 or response2.status_code != 200:
                print(f"❌ HTTP errors: {response1.status_code}, {response2.status_code}")
                return False
            
            print(f"✅ Performance test passed")
            print(f"   First request: {first_time:.3f}s")
            print(f"   Second request: {second_time:.3f}s")
            
            # Performance should be reasonable
            if first_time > 5.0:
                print(f"⚠️  First request took longer than expected: {first_time:.3f}s")
            
            if second_time > 5.0:
                print(f"⚠️  Second request took longer than expected: {second_time:.3f}s")
            
            return True
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            return False


async def test_claude_scenario_simulation():
    """Simulate how Claude would use the narrator context"""
    server_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print("🧠 Testing Claude usage scenario...")
            
            # Get narrator context
            response = await client.get(f"{server_url}/narrator/context")
            if response.status_code != 200:
                print(f"❌ Failed to get narrator context: HTTP {response.status_code}")
                return False
            
            context = response.json()
            
            # Simulate Claude analysis
            budget_status = context.get("budget_status", {})
            days_remaining = budget_status.get("days_remaining", 0)
            urgent_items = context.get("urgent_items", [])
            recommendations = context.get("recommendations", [])
            
            # Decision making logic (simulating Claude's thought process)
            decision_analysis = {
                "budget_situation": "unknown",
                "urgency_level": "normal",
                "recommended_action": "continue_normal_work",
                "time_horizon": "long_term"
            }
            
            # Budget analysis
            if days_remaining < 1:
                decision_analysis["budget_situation"] = "critical"
                decision_analysis["urgency_level"] = "immediate"
                decision_analysis["recommended_action"] = "emergency_mode_only"
                decision_analysis["time_horizon"] = "immediate"
            elif days_remaining < 2:
                decision_analysis["budget_situation"] = "warning"
                decision_analysis["urgency_level"] = "high"
                decision_analysis["recommended_action"] = "high_value_only"
                decision_analysis["time_horizon"] = "today"
            elif days_remaining < 5:
                decision_analysis["budget_situation"] = "caution"
                decision_analysis["urgency_level"] = "elevated"
                decision_analysis["recommended_action"] = "selective_work"
                decision_analysis["time_horizon"] = "this_week"
            else:
                decision_analysis["budget_situation"] = "healthy"
                decision_analysis["time_horizon"] = "long_term"
            
            # Urgency analysis
            if urgent_items:
                decision_analysis["urgency_level"] = "high"
                decision_analysis["recommended_action"] = f"address_{len(urgent_items)}_urgent_items"
            
            print(f"✅ Claude scenario simulation passed")
            print(f"   Budget situation: {decision_analysis['budget_situation']}")
            print(f"   Urgency level: {decision_analysis['urgency_level']}")
            print(f"   Recommended action: {decision_analysis['recommended_action']}")
            print(f"   Time horizon: {decision_analysis['time_horizon']}")
            print(f"   Days remaining: {days_remaining:.1f}")
            print(f"   Urgent items: {len(urgent_items)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Claude scenario test failed: {e}")
            return False


async def test_narrator_context_with_errors():
    """Test narrator context error handling"""
    server_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print("🔧 Testing error handling...")
            
            # Test with valid endpoint
            response = await client.get(f"{server_url}/narrator/context")
            
            # Should always return 200 even if some subsystems are down
            if response.status_code != 200:
                print(f"❌ Expected 200, got {response.status_code}")
                return False
            
            data = response.json()
            
            # Should have fallback values even if some services fail
            if not isinstance(data.get("summary"), str):
                print("❌ Summary should always be a string")
                return False
            
            if not isinstance(data.get("urgent_items"), list):
                print("❌ Urgent items should always be a list")
                return False
            
            if not isinstance(data.get("recommendations"), list):
                print("❌ Recommendations should always be a list")
                return False
            
            print(f"✅ Error handling test passed")
            print(f"   Response includes fallback values")
            
            return True
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False


async def main():
    """Run all narrator context tests"""
    print("🧠 Simple Narrator Context Test Suite")
    print("=" * 50)
    
    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health_response = await client.get("http://localhost:8000/health")
            if health_response.status_code != 200:
                print("❌ MCP server is not responding. Please start it with:")
                print("   source venv/bin/activate && python mcp_server.py")
                return False
            print("✅ MCP server is running")
    except Exception as e:
        print(f"❌ Cannot connect to MCP server: {e}")
        print("Please start the server with: source venv/bin/activate && python mcp_server.py")
        return False
    
    print()
    
    # Run tests
    tests = [
        ("Basic narrator context", test_narrator_context_basic),
        ("Performance test", test_narrator_context_performance), 
        ("Claude scenario simulation", test_claude_scenario_simulation),
        ("Error handling", test_narrator_context_with_errors)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            success = await test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} passed")
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
        print()
    
    # Summary
    print("=" * 50)
    print("📊 Test Results")
    print(f"Passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 All narrator context tests passed!")
        print("🧠 Narrator context is ready for Claude integration")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)