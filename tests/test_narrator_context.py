#!/usr/bin/env python3
"""
Narrator Context Testing for Mecris
Tests the narrator context functionality and Claude integration scenarios
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os
import sys
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


class TestNarratorContext(unittest.TestCase):
    """Test narrator context functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.server_url = "http://localhost:8000"
        
        # Mock data for testing
        self.mock_goals = [
            {"id": "1", "title": "Test Goal 1", "status": "active"},
            {"id": "2", "title": "Test Goal 2", "status": "active"},
            {"id": "3", "title": "Completed Goal", "status": "completed"}
        ]
        
        self.mock_todos = [
            {"title": "Todo 1", "completed": False},
            {"title": "Todo 2", "completed": False},
            {"title": "Done Todo", "completed": True}
        ]
        
        self.mock_beeminder_goals = [
            {
                "slug": "test-goal-1",
                "title": "Test Beeminder Goal 1", 
                "derail_risk": "SAFE",
                "safebuf": 5
            },
            {
                "slug": "critical-goal",
                "title": "Critical Goal",
                "derail_risk": "CRITICAL", 
                "safebuf": 0
            }
        ]
        
        self.mock_budget_status = {
            "remaining_budget": 10.50,
            "days_remaining": 3.5,
            "total_budget": 20.0,
            "used_budget": 9.50
        }
    
    def tearDown(self):
        """Clean up"""
        pass
    
    async def test_narrator_context_endpoint_structure(self):
        """Test that narrator context endpoint returns correct structure"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.server_url}/narrator/context")
                self.assertEqual(response.status_code, 200)
                
                data = response.json()
                
                # Check required fields are present
                required_fields = [
                    "summary", "goals_status", "urgent_items", 
                    "beeminder_alerts", "goal_runway", "budget_status",
                    "recommendations", "last_updated"
                ]
                
                for field in required_fields:
                    self.assertIn(field, data, f"Missing required field: {field}")
                
                # Check data types
                self.assertIsInstance(data["summary"], str)
                self.assertIsInstance(data["goals_status"], dict)
                self.assertIsInstance(data["urgent_items"], list)
                self.assertIsInstance(data["beeminder_alerts"], list)
                self.assertIsInstance(data["goal_runway"], list)
                self.assertIsInstance(data["budget_status"], dict)
                self.assertIsInstance(data["recommendations"], list)
                
                print(f"✅ Narrator context structure valid")
                print(f"   Summary: {data['summary'][:50]}...")
                print(f"   Urgent items: {len(data['urgent_items'])}")
                print(f"   Recommendations: {len(data['recommendations'])}")
                
                return data
                
            except Exception as e:
                self.fail(f"Narrator context endpoint failed: {e}")
    
    @patch('usage_tracker.get_budget_status')
    @patch('usage_tracker.get_goals')
    async def test_narrator_context_budget_warnings(self, mock_get_goals, mock_budget_status):
        """Test narrator context with different budget scenarios"""
        # Mock internal functions
        mock_get_goals.return_value = self.mock_goals
        
        # Test critical budget scenario
        critical_budget = {
            "remaining_budget": 0.50,
            "days_remaining": 0.5,
            "total_budget": 20.0,
            "used_budget": 19.50
        }
        
        mock_budget_status.return_value = critical_budget
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.server_url}/narrator/context")
                data = response.json()
                
                # Should have budget critical warning
                urgent_items = data.get("urgent_items", [])
                budget_urgents = [item for item in urgent_items if "BUDGET CRITICAL" in item]
                self.assertTrue(len(budget_urgents) > 0, "Should have critical budget warning")
                
                # Should have budget recommendation
                recommendations = data.get("recommendations", [])
                budget_recs = [rec for rec in recommendations if "budget constraints" in rec.lower()]
                self.assertTrue(len(budget_recs) > 0, "Should have budget-related recommendation")
                
                print(f"✅ Critical budget scenario handled correctly")
                
            except Exception as e:
                self.fail(f"Budget warning test failed: {e}")
    
    async def test_narrator_context_performance(self):
        """Test narrator context response time and caching"""
        import time
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Make multiple requests to test caching
                start_time = time.time()
                response1 = await client.get(f"{self.server_url}/narrator/context")
                first_request_time = time.time() - start_time
                
                start_time = time.time()
                response2 = await client.get(f"{self.server_url}/narrator/context")
                second_request_time = time.time() - start_time
                
                # Both should succeed
                self.assertEqual(response1.status_code, 200)
                self.assertEqual(response2.status_code, 200)
                
                # Performance check - requests should be reasonably fast
                self.assertLess(first_request_time, 5.0, "First request took too long")
                self.assertLess(second_request_time, 5.0, "Second request took too long")
                
                print(f"✅ Performance test passed")
                print(f"   First request: {first_request_time:.2f}s")
                print(f"   Second request: {second_request_time:.2f}s")
                
                # Compare data consistency
                data1 = response1.json()
                data2 = response2.json()
                
                # Last updated should be similar (within 10 seconds)
                time1 = datetime.fromisoformat(data1["last_updated"].replace('Z', '+00:00'))
                time2 = datetime.fromisoformat(data2["last_updated"].replace('Z', '+00:00'))
                time_diff = abs((time2 - time1).total_seconds())
                self.assertLess(time_diff, 10, "Response times too far apart")
                
            except Exception as e:
                self.fail(f"Performance test failed: {e}")
    
    async def test_narrator_context_error_handling(self):
        """Test narrator context with various error conditions"""
        # Test when server is running but some services might be down
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.server_url}/narrator/context")
                
                # Should always return 200 even if some subsystems fail
                self.assertEqual(response.status_code, 200)
                
                data = response.json()
                
                # Should have fallback values
                self.assertIsInstance(data["summary"], str)
                self.assertIsInstance(data["urgent_items"], list)
                self.assertIsInstance(data["recommendations"], list)
                
                print(f"✅ Error handling test passed")
                print(f"   Summary: {data['summary']}")
                
            except Exception as e:
                self.fail(f"Error handling test failed: {e}")


class TestClaudeNarratorIntegration(unittest.TestCase):
    """Test scenarios that simulate Claude narrator usage"""
    
    def setUp(self):
        """Set up test environment"""
        self.server_url = "http://localhost:8000"
    
    def tearDown(self):
        """Clean up"""
        pass
    
    async def test_claude_context_consumption_scenario(self):
        """Test a scenario that simulates how Claude would consume context"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Get narrator context
                response = await client.get(f"{self.server_url}/narrator/context")
                self.assertEqual(response.status_code, 200)
                
                context = response.json()
                
                # Simulate Claude processing the context
                claude_analysis = self._simulate_claude_analysis(context)
                
                # Verify Claude can extract useful information
                self.assertIsInstance(claude_analysis["priority_tasks"], list)
                self.assertIsInstance(claude_analysis["time_management"], str)
                self.assertIsInstance(claude_analysis["budget_recommendation"], str)
                
                print(f"✅ Claude context consumption simulation passed")
                print(f"   Priority tasks identified: {len(claude_analysis['priority_tasks'])}")
                print(f"   Time management: {claude_analysis['time_management']}")
                print(f"   Budget recommendation: {claude_analysis['budget_recommendation'][:50]}...")
                
                return claude_analysis
                
            except Exception as e:
                self.fail(f"Claude context consumption test failed: {e}")
    
    def _simulate_claude_analysis(self, context):
        """Simulate how Claude would analyze the narrator context"""
        analysis = {
            "priority_tasks": [],
            "time_management": "",
            "budget_recommendation": ""
        }
        
        # Extract urgent items as priority tasks
        urgent_items = context.get("urgent_items", [])
        analysis["priority_tasks"] = urgent_items
        
        # Analyze budget situation
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        
        if days_remaining < 1:
            analysis["time_management"] = "CRITICAL: Less than 1 day of budget remaining"
            analysis["budget_recommendation"] = "Emergency mode: Focus only on absolutely critical tasks"
        elif days_remaining < 2:
            analysis["time_management"] = "URGENT: Less than 2 days of budget remaining"
            analysis["budget_recommendation"] = "High priority mode: Focus on high-value work only"
        elif days_remaining < 5:
            analysis["time_management"] = "CAUTION: Less than 5 days of budget remaining"
            analysis["budget_recommendation"] = "Selective mode: Choose tasks carefully"
        else:
            analysis["time_management"] = "NORMAL: Sufficient budget remaining"
            analysis["budget_recommendation"] = "Standard mode: All task types acceptable"
        
        return analysis
    
    async def test_narrator_decision_making_scenarios(self):
        """Test decision-making scenarios based on narrator context"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Get current context
                response = await client.get(f"{self.server_url}/narrator/context")
                context = response.json()
                
                # Test different decision scenarios
                scenarios = [
                    {
                        "name": "Should I work on a complex feature?",
                        "test": lambda ctx: self._should_work_on_complex_task(ctx),
                        "expect_type": bool
                    },
                    {
                        "name": "What's my time horizon?", 
                        "test": lambda ctx: self._get_time_horizon(ctx),
                        "expect_type": str
                    },
                    {
                        "name": "What should I prioritize?",
                        "test": lambda ctx: self._get_prioritization_advice(ctx),
                        "expect_type": str
                    }
                ]
                
                for scenario in scenarios:
                    result = scenario["test"](context)
                    self.assertIsInstance(result, scenario["expect_type"])
                    print(f"✅ {scenario['name']}: {str(result)[:60]}...")
                
                print(f"✅ All decision-making scenarios passed")
                
            except Exception as e:
                self.fail(f"Decision-making test failed: {e}")
    
    def _should_work_on_complex_task(self, context):
        """Simulate decision: should I work on a complex task?"""
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        urgent_items = context.get("urgent_items", [])
        
        # Don't do complex work if budget is critical or there are urgent items
        if days_remaining < 1 or len(urgent_items) > 0:
            return False
        
        # Only do complex work if we have reasonable budget
        return days_remaining > 2
    
    def _get_time_horizon(self, context):
        """Get the appropriate time horizon for planning"""
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        
        if days_remaining < 1:
            return "immediate" 
        elif days_remaining < 2:
            return "today"
        elif days_remaining < 5:
            return "this_week"
        else:
            return "multiple_weeks"
    
    def _get_prioritization_advice(self, context):
        """Get prioritization advice based on context"""
        urgent_items = context.get("urgent_items", [])
        recommendations = context.get("recommendations", [])
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        
        if urgent_items:
            return f"URGENT: Address {len(urgent_items)} critical items first"
        elif days_remaining < 2:
            return "BUDGET CRITICAL: Focus on highest-value work only"
        elif recommendations:
            return f"Follow system recommendations: {recommendations[0][:40]}..."
        else:
            return "Standard prioritization: Work on active goals"


def run_narrator_tests():
    """Run all narrator context tests"""
    print("🧠 Running Narrator Context Test Suite")
    print("=" * 50)
    
    async def run_async_tests():
        # Create test suite
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Add test classes
        suite.addTests(loader.loadTestsFromTestCase(TestNarratorContext))
        suite.addTests(loader.loadTestsFromTestCase(TestClaudeNarratorIntegration))
        
        # Create a custom test runner that handles async tests
        results = []
        
        for test_case in suite:
            if hasattr(test_case, '_testMethodName'):
                method = getattr(test_case, test_case._testMethodName)
                if asyncio.iscoroutinefunction(method):
                    try:
                        await method()
                        results.append(("PASS", str(test_case)))
                        print(f"✅ {test_case}")
                    except Exception as e:
                        results.append(("FAIL", str(test_case), str(e)))
                        print(f"❌ {test_case}: {e}")
                else:
                    try:
                        method()
                        results.append(("PASS", str(test_case)))
                        print(f"✅ {test_case}")
                    except Exception as e:
                        results.append(("FAIL", str(test_case), str(e)))
                        print(f"❌ {test_case}: {e}")
        
        # Summary
        passed = len([r for r in results if r[0] == "PASS"])
        failed = len([r for r in results if r[0] == "FAIL"])
        
        print("\n" + "=" * 50)
        print("📊 Narrator Context Test Results")
        print(f"Tests run: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        if failed > 0:
            print("\n❌ FAILURES:")
            for result in results:
                if result[0] == "FAIL":
                    print(f"  • {result[1]}: {result[2]}")
        
        success = failed == 0
        if success:
            print("\n✅ All narrator context tests passed!")
            print("🧠 Narrator context functionality is working correctly")
        else:
            print(f"\n⚠️ {failed} test(s) failed")
        
        return success
    
    return asyncio.run(run_async_tests())


if __name__ == "__main__":
    success = run_narrator_tests()
    exit(0 if success else 1)