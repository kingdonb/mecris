#!/usr/bin/env python3
"""
Mecris System Test Suite
Comprehensive testing for all Mecris components
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

import httpx
from dotenv import load_dotenv

# Import our modules
from obsidian_client import ObsidianMCPClient
from beeminder_client import BeeminderClient
from claude_monitor import ClaudeMonitor
from twilio_sender import send_sms

load_dotenv()

class MecrisTestSuite:
    """Comprehensive test suite for Mecris system"""
    
    def __init__(self):
        self.results = []
        self.server_url = f"http://localhost:{os.getenv('PORT', 8000)}"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def log_test(self, component: str, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        result = {
            "component": component,
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {component}: {test_name}")
        if details and not success:
            print(f"    Details: {details}")
    
    async def test_server_health(self):
        """Test MCP server health endpoint"""
        try:
            response = await self.client.get(f"{self.server_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                self.log_test("Server", "Health Check", True, f"Status: {health_data.get('status')}")
                
                # Check individual service health
                services = health_data.get("services", {})
                for service, status in services.items():
                    self.log_test("Server", f"{service.title()} Service", 
                                status == "ok", f"Status: {status}")
            else:
                self.log_test("Server", "Health Check", False, 
                            f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Server", "Health Check", False, str(e))
    
    async def test_obsidian_integration(self):
        """Test Obsidian MCP client integration"""
        client = ObsidianMCPClient()
        
        try:
            # Test health check
            health = await client.health_check()
            self.log_test("Obsidian", "Health Check", health == "ok", f"Status: {health}")
            
            # Test goals extraction
            goals = await client.get_goals()
            self.log_test("Obsidian", "Goals Extraction", isinstance(goals, list), 
                        f"Found {len(goals)} goals")
            
            # Test todos extraction  
            todos = await client.get_todos()
            self.log_test("Obsidian", "Todos Extraction", isinstance(todos, list),
                        f"Found {len(todos)} todos")
            
            # Test daily note (today)
            today = datetime.now().strftime("%Y-%m-%d")
            daily_note = await client.get_daily_note(today)
            self.log_test("Obsidian", "Daily Note Access", isinstance(daily_note, str),
                        f"Note length: {len(daily_note)} chars")
            
        except Exception as e:
            self.log_test("Obsidian", "Integration Test", False, str(e))
        finally:
            await client.close()
    
    async def test_beeminder_integration(self):
        """Test Beeminder API client integration"""
        client = BeeminderClient()
        
        try:
            # Test health check
            health = await client.health_check()
            self.log_test("Beeminder", "Health Check", health in ["ok", "not_configured"], 
                        f"Status: {health}")
            
            if health == "ok":
                # Test goals retrieval
                goals = await client.get_all_goals()
                self.log_test("Beeminder", "Goals Retrieval", isinstance(goals, list),
                            f"Found {len(goals)} goals")
                
                # Test emergencies detection
                emergencies = await client.get_emergencies()
                self.log_test("Beeminder", "Emergency Detection", isinstance(emergencies, list),
                            f"Found {len(emergencies)} emergencies")
                
                # Test emergency summary
                summary = await client.format_emergency_summary()
                self.log_test("Beeminder", "Emergency Summary", isinstance(summary, str),
                            f"Summary: {summary[:50]}...")
            else:
                self.log_test("Beeminder", "API Integration", False, 
                            "Beeminder credentials not configured")
            
        except Exception as e:
            self.log_test("Beeminder", "Integration Test", False, str(e))
        finally:
            await client.close()
    
    async def test_claude_monitor(self):
        """Test Claude credit monitoring"""
        monitor = ClaudeMonitor()
        
        try:
            # Test health check
            health = await monitor.health_check()
            self.log_test("Claude Monitor", "Health Check", health == "ok", f"Status: {health}")
            
            # Test current usage
            usage = await monitor.get_current_usage()
            self.log_test("Claude Monitor", "Usage Retrieval", usage is not None,
                        f"Credits remaining: ${usage.credits_remaining:.2f}" if usage else "Failed")
            
            # Test usage summary
            summary = await monitor.get_usage_summary()
            self.log_test("Claude Monitor", "Usage Summary", "error" not in summary,
                        f"Status: {summary.get('status', 'unknown')}")
            
            # Test manual usage recording (small test amount)
            test_cost = 0.01
            record_success = await monitor.record_usage(test_cost, "Test recording")
            self.log_test("Claude Monitor", "Usage Recording", record_success,
                        f"Recorded ${test_cost} test cost")
            
        except Exception as e:
            self.log_test("Claude Monitor", "Integration Test", False, str(e))
        finally:
            await monitor.close()
    
    def test_twilio_integration(self):
        """Test Twilio SMS integration (dry run)"""
        try:
            # Check environment variables
            required_vars = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", 
                           "TWILIO_FROM_NUMBER", "TWILIO_TO_NUMBER"]
            
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                self.log_test("Twilio", "Configuration Check", False,
                            f"Missing: {', '.join(missing_vars)}")
            else:
                self.log_test("Twilio", "Configuration Check", True,
                            "All required variables present")
                
                # Test SMS sending (commented out to avoid spam)
                # test_success = send_sms("🧪 Mecris test message - please ignore")
                # self.log_test("Twilio", "SMS Sending", test_success, "Test message sent")
                
                self.log_test("Twilio", "SMS Capability", True, 
                            "Ready to send (test disabled to avoid spam)")
            
        except Exception as e:
            self.log_test("Twilio", "Integration Test", False, str(e))
    
    async def test_api_endpoints(self):
        """Test all API endpoints"""
        endpoints = [
            ("GET", "/", "Root Endpoint"),
            ("GET", "/health", "Health Check"),
            ("GET", "/goals", "Goals API"),
            ("GET", "/todos", "Todos API"), 
            ("GET", "/beeminder/status", "Beeminder Status"),
            ("GET", "/beeminder/emergency", "Beeminder Emergency"),
            ("GET", "/budget/status", "Budget Status"),
            ("GET", "/narrator/context", "Narrator Context")
        ]
        
        for method, endpoint, name in endpoints:
            try:
                if method == "GET":
                    response = await self.client.get(f"{self.server_url}{endpoint}")
                
                success = response.status_code == 200
                details = f"HTTP {response.status_code}"
                
                if success and endpoint == "/narrator/context":
                    # Special validation for narrator context
                    data = response.json()
                    required_fields = ["summary", "urgent_items", "recommendations"]
                    has_required = all(field in data for field in required_fields)
                    if not has_required:
                        success = False
                        details += " - Missing required fields"
                
                self.log_test("API", name, success, details)
                
            except Exception as e:
                self.log_test("API", name, False, str(e))
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r["success"]])
        failed_tests = total_tests - passed_tests
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Group by component
        components = {}
        for result in self.results:
            comp = result["component"]
            if comp not in components:
                components[comp] = {"passed": 0, "failed": 0, "tests": []}
            
            if result["success"]:
                components[comp]["passed"] += 1
            else:
                components[comp]["failed"] += 1
            
            components[comp]["tests"].append(result)
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": f"{success_rate:.1f}%",
                "timestamp": datetime.now().isoformat()
            },
            "components": components,
            "failed_tests": [r for r in self.results if not r["success"]],
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for failed health checks
        health_failures = [r for r in self.results 
                         if not r["success"] and "Health Check" in r["test"]]
        
        if health_failures:
            recommendations.append("❗ Health check failures detected - verify service configurations")
        
        # Check for API failures
        api_failures = [r for r in self.results 
                       if not r["success"] and r["component"] == "API"]
        
        if api_failures:
            recommendations.append("❗ API endpoint failures - check server startup and dependencies")
        
        # Check for configuration issues
        config_failures = [r for r in self.results 
                         if not r["success"] and "not_configured" in r["details"]]
        
        if config_failures:
            recommendations.append("⚙️ Configuration incomplete - review .env file and service credentials")
        
        # Success case
        if not any(not r["success"] for r in self.results):
            recommendations.append("✅ All tests passed - Mecris system is fully operational!")
        
        return recommendations
    
    async def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 Starting Mecris System Test Suite")
        print("=" * 50)
        
        # Test individual components
        await self.test_obsidian_integration()
        await self.test_beeminder_integration()
        await self.test_claude_monitor()
        self.test_twilio_integration()
        
        # Test server if running
        try:
            await self.test_server_health()
            await self.test_api_endpoints()
        except Exception as e:
            self.log_test("Server", "Connection", False, 
                        f"Server not running on {self.server_url}")
        
        # Generate report
        report = self.generate_report()
        
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        summary = report["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']} ✅")
        print(f"Failed: {summary['failed']} ❌")
        print(f"Success Rate: {summary['success_rate']}")
        
        if report["failed_tests"]:
            print(f"\n❌ FAILED TESTS ({len(report['failed_tests'])}):")
            for test in report["failed_tests"]:
                print(f"  • {test['component']}: {test['test']} - {test['details']}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"  {rec}")
        
        # Save detailed report
        report_file = f"mecris_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return report
    
    async def close(self):
        """Clean up resources"""
        await self.client.aclose()

async def main():
    """Main test runner"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
Mecris System Test Suite

Usage:
  python test_mecris.py              # Run all tests
  python test_mecris.py --help       # Show this help

Environment:
  Make sure .env file is configured with all required credentials.
  Start mcp_server.py before running API tests.

Test Categories:
  - Obsidian MCP integration
  - Beeminder API client  
  - Claude budget monitoring
  - Twilio SMS alerts (dry run)
  - Server health checks
  - API endpoint validation
        """)
        return
    
    test_suite = MecrisTestSuite()
    
    try:
        report = await test_suite.run_all_tests()
        
        # Exit with appropriate code
        if report["summary"]["failed"] == 0:
            print("\n🎉 All systems operational!")
            sys.exit(0)
        else:
            print(f"\n⚠️ {report['summary']['failed']} test(s) failed - review configuration")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test suite crashed: {e}")
        sys.exit(1)
    finally:
        await test_suite.close()

if __name__ == "__main__":
    asyncio.run(main())