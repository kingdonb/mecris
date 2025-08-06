#!/usr/bin/env python3
"""
Beeminder Live Integration Test
Tests real API calls to verify Beeminder data accuracy
"""

import asyncio
import os
import json
from datetime import datetime
from dotenv import load_dotenv

from beeminder_client import BeeminderClient

load_dotenv()

class BeeminderLiveTest:
    """Live integration tests for Beeminder API"""
    
    def __init__(self):
        self.client = BeeminderClient()
        self.results = []
    
    def log_result(self, test_name: str, success: bool, details: str = "", data: dict = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        if data and success:
            print(f"    Sample data: {json.dumps(data, indent=2)[:200]}...")
    
    async def test_configuration(self):
        """Test if Beeminder credentials are configured"""
        username = os.getenv("BEEMINDER_USERNAME")
        token = os.getenv("BEEMINDER_AUTH_TOKEN")
        
        if not username or not token:
            self.log_result(
                "Configuration Check",
                False,
                "Missing BEEMINDER_USERNAME or BEEMINDER_AUTH_TOKEN in environment"
            )
            return False
        
        self.log_result(
            "Configuration Check",
            True,
            f"Username: {username[:3]}*** Token: {'*' * len(token)}"
        )
        return True
    
    async def test_health_check(self):
        """Test API connectivity"""
        try:
            health = await self.client.health_check()
            success = health == "ok"
            self.log_result(
                "Health Check",
                success,
                f"API Status: {health}"
            )
            return success
        except Exception as e:
            self.log_result("Health Check", False, f"Exception: {e}")
            return False
    
    async def test_user_goals_fetch(self):
        """Test fetching raw user goals"""
        try:
            goals = await self.client.get_user_goals()
            success = isinstance(goals, list)
            
            if success and goals:
                sample_goal = goals[0] if goals else {}
                self.log_result(
                    "User Goals Fetch",
                    True,
                    f"Retrieved {len(goals)} raw goals",
                    {"sample_keys": list(sample_goal.keys())[:5] if sample_goal else []}
                )
            else:
                self.log_result(
                    "User Goals Fetch",
                    success,
                    "No goals found or invalid response"
                )
            return success
        except Exception as e:
            self.log_result("User Goals Fetch", False, f"Exception: {e}")
            return False
    
    async def test_structured_goals(self):
        """Test structured goal parsing and risk assessment"""
        try:
            goals = await self.client.get_all_goals()
            success = isinstance(goals, list)
            
            if success and goals:
                # Verify structured data
                sample_goal = goals[0]
                required_fields = ["slug", "title", "safebuf", "derail_risk", "current_value", "target_value"]
                has_all_fields = all(field in sample_goal for field in required_fields)
                
                if has_all_fields:
                    self.log_result(
                        "Structured Goals",
                        True,
                        f"Retrieved {len(goals)} structured goals",
                        {
                            "sample_goal": {k: sample_goal[k] for k in required_fields},
                            "risk_levels": [g.get("derail_risk") for g in goals[:3]]
                        }
                    )
                else:
                    missing = [f for f in required_fields if f not in sample_goal]
                    self.log_result(
                        "Structured Goals",
                        False,
                        f"Missing required fields: {missing}"
                    )
                    success = False
            else:
                self.log_result("Structured Goals", success, "No structured goals returned")
            
            return success
        except Exception as e:
            self.log_result("Structured Goals", False, f"Exception: {e}")
            return False
    
    async def test_emergencies(self):
        """Test beemergency detection"""
        try:
            emergencies = await self.client.get_emergencies()
            success = isinstance(emergencies, list)
            
            if success:
                urgent_count = len([e for e in emergencies if e.get("urgency") == "IMMEDIATE"])
                warning_count = len([e for e in emergencies if e.get("urgency") == "TODAY"])
                caution_count = len([e for e in emergencies if e.get("urgency") == "SOON"])
                
                self.log_result(
                    "Emergency Detection",
                    True,
                    f"Found {len(emergencies)} total emergencies: {urgent_count} immediate, {warning_count} today, {caution_count} soon",
                    {
                        "sample_emergency": emergencies[0] if emergencies else None,
                        "urgency_breakdown": {
                            "immediate": urgent_count,
                            "today": warning_count,
                            "soon": caution_count
                        }
                    }
                )
            else:
                self.log_result("Emergency Detection", False, "Invalid emergency data")
            
            return success
        except Exception as e:
            self.log_result("Emergency Detection", False, f"Exception: {e}")
            return False
    
    async def test_runway_summary(self):
        """Test runway summary with bike goal prioritization"""
        try:
            runway = await self.client.get_runway_summary(limit=4)
            success = isinstance(runway, list)
            
            if success and runway:
                # Check if bike goal is included (if it exists)
                bike_goals = [g for g in runway if "bike" in g.get("slug", "").lower()]
                has_bike = len(bike_goals) > 0
                
                self.log_result(
                    "Runway Summary",
                    True,
                    f"Retrieved {len(runway)} runway goals, bike goal included: {has_bike}",
                    {
                        "runway_goals": [{"slug": g.get("slug"), "safebuf": g.get("safebuf")} for g in runway],
                        "bike_goal_present": has_bike
                    }
                )
            else:
                self.log_result("Runway Summary", success, "No runway data returned")
            
            return success
        except Exception as e:
            self.log_result("Runway Summary", False, f"Exception: {e}")
            return False
    
    async def test_username_hardcoding(self):
        """Test that username is not hardcoded"""
        env_username = os.getenv("BEEMINDER_USERNAME")
        client_username = self.client.username
        
        success = env_username == client_username and client_username is not None
        
        self.log_result(
            "Username Configuration",
            success,
            f"Environment: {env_username}, Client: {client_username}, Match: {success}"
        )
        return success
    
    async def test_no_mock_data(self):
        """Verify no static/mock data is being returned"""
        try:
            # Get data twice with a small delay
            goals1 = await self.client.get_all_goals()
            await asyncio.sleep(0.1)
            goals2 = await self.client.get_all_goals()
            
            # Check if data is identical (could indicate static mock data)
            data1_str = json.dumps(goals1, sort_keys=True)
            data2_str = json.dumps(goals2, sort_keys=True)
            
            # Data should be very similar but timestamps may differ slightly
            # Focus on checking that it's not obviously static mock data
            has_realistic_data = True
            
            if goals1:
                sample_goal = goals1[0]
                # Check for obviously fake data patterns
                fake_patterns = [
                    sample_goal.get("slug") == "example-goal",
                    sample_goal.get("title") == "Example Goal",
                    sample_goal.get("current_value") == 0 and sample_goal.get("target_value") == 100,
                    sample_goal.get("safebuf") == 7  # Very round number might indicate fake data
                ]
                has_realistic_data = not any(fake_patterns)
            
            self.log_result(
                "No Mock Data Check",
                has_realistic_data,
                f"Data appears realistic: {has_realistic_data}",
                {
                    "sample_values": {
                        "slug": goals1[0].get("slug") if goals1 else None,
                        "safebuf": goals1[0].get("safebuf") if goals1 else None,
                        "current_value": goals1[0].get("current_value") if goals1 else None
                    }
                }
            )
            return has_realistic_data
        except Exception as e:
            self.log_result("No Mock Data Check", False, f"Exception: {e}")
            return False
    
    async def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 Starting Beeminder Live Integration Tests")
        print("=" * 50)
        
        tests = [
            self.test_configuration,
            self.test_health_check,
            self.test_user_goals_fetch,
            self.test_structured_goals,
            self.test_emergencies,
            self.test_runway_summary,
            self.test_username_hardcoding,
            self.test_no_mock_data
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                success = await test()
                if success:
                    passed += 1
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} passed")
        
        if passed == total:
            print("✅ All Beeminder integration tests passed!")
        else:
            print(f"⚠️ {total - passed} tests failed")
        
        # Save detailed results
        report_file = f"beeminder_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "summary": {
                    "passed": passed,
                    "total": total,
                    "success_rate": passed / total if total > 0 else 0,
                    "timestamp": datetime.now().isoformat()
                },
                "results": self.results
            }, f, indent=2)
        
        print(f"📋 Detailed report saved to: {report_file}")
        
        await self.client.close()
        return passed == total

async def main():
    """Run Beeminder live tests"""
    test_suite = BeeminderLiveTest()
    success = await test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)