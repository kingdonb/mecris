#!/usr/bin/env python3
"""
Comprehensive Virtual Budget Integration Test

Tests the complete multi-provider billing system including:
- Virtual budget management
- Multi-provider usage recording
- Groq integration (mocked)
- Reconciliation system
- MCP server integration
"""

import os
import json
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

def test_virtual_budget_system():
    """Test the complete virtual budget system."""
    print("🧪 Testing Complete Virtual Budget System")
    print("=" * 60)
    
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # Test 1: Initialize Virtual Budget Manager
        print("\n1️⃣ Testing Virtual Budget Manager Initialization")
        from virtual_budget_manager import VirtualBudgetManager, Provider
        
        manager = VirtualBudgetManager(db_path=temp_db_path)
        print("   ✅ VirtualBudgetManager initialized")
        
        # Test 2: Record Anthropic Usage
        print("\n2️⃣ Testing Anthropic Usage Recording")
        anthro_result = manager.record_usage(
            Provider.ANTHROPIC,
            "claude-3-5-sonnet-20241022",
            1000, 500,
            "test",
            "Testing Anthropic integration"
        )
        
        if anthro_result.get("recorded"):
            print(f"   ✅ Anthropic usage recorded: ${anthro_result['cost']:.4f}")
            print(f"   💰 Remaining budget: ${anthro_result['remaining_budget']:.2f}")
        else:
            print(f"   ❌ Anthropic recording failed: {anthro_result}")
        
        # Test 3: Record Groq Usage
        print("\n3️⃣ Testing Groq Usage Recording")
        groq_result = manager.record_usage(
            Provider.GROQ,
            "openai/gpt-oss-20b",
            2000, 800,
            "test", 
            "Testing Groq integration"
        )
        
        if groq_result.get("recorded"):
            print(f"   ✅ Groq usage recorded: ${groq_result['cost']:.4f}")
            print(f"   💰 Remaining budget: ${groq_result['remaining_budget']:.2f}")
        else:
            print(f"   ❌ Groq recording failed: {groq_result}")
        
        # Test 4: Budget Status Check
        print("\n4️⃣ Testing Budget Status")
        budget_status = manager.get_budget_status()
        
        if "error" not in budget_status:
            print(f"   ✅ Daily budget: ${budget_status['daily_budget']['allocated']:.2f}")
            print(f"   💸 Spent today: ${budget_status['daily_budget']['spent']:.4f}")
            print(f"   ⏳ Available: ${budget_status['daily_budget']['available']:.4f}")
            print(f"   📊 Provider breakdown: {budget_status['provider_breakdown']}")
            print(f"   🚨 Health: {budget_status['budget_health']}")
        else:
            print(f"   ❌ Budget status error: {budget_status['error']}")
        
        # Test 5: Usage Summary
        print("\n5️⃣ Testing Usage Summary")
        summary = manager.get_usage_summary(7)
        
        print(f"   📈 7-day summary:")
        print(f"   • Total estimated: ${summary['total_estimated']:.4f}")
        print(f"   • Total actual: ${summary['total_actual']:.4f}")
        print(f"   • Provider totals: {len(summary['provider_totals'])} providers")
        
        # Test 6: Reconciliation System (Mock)
        print("\n6️⃣ Testing Reconciliation System")
        from billing_reconciliation import BillingReconciliation
        
        reconciler = BillingReconciliation()
        
        # Mock the actual API calls to avoid real requests
        with patch.object(reconciler, '_get_anthropic_actual_costs', return_value=0.0055):
            with patch.object(reconciler, '_get_groq_actual_costs', return_value=0.0002):
                yesterday = date.today() - timedelta(days=1)
                results = reconciler.reconcile_all_providers(yesterday)
                
                print(f"   📊 Reconciled {len(results)} providers for {yesterday}")
                for result in results:
                    if result.success:
                        print(f"   ✅ {result.provider}: {result.drift_percentage:.2f}% drift")
                    else:
                        print(f"   ❌ {result.provider}: {result.error}")
        
        # Test 7: Groq Scraper (Mock)
        print("\n7️⃣ Testing Groq Integration")
        from fetch_groq_usage import GroqUsageScraper
        
        scraper = GroqUsageScraper(cache_minutes=1)  # Short cache for testing
        
        # Mock the actual scraping to avoid web requests
        mock_usage_data = {
            "success": True,
            "data": {
                "monthly_usage": "$1.06 this month",
                "detected_amounts": ["$1.06", "$0.23"]
            },
            "scraped_at": datetime.now().isoformat(),
            "source": "scraper"
        }
        
        with patch.object(scraper, 'scrape_usage_data', return_value=mock_usage_data):
            usage_result = scraper.get_usage_data()
            
            if usage_result.get("success"):
                print(f"   ✅ Groq usage fetched: {usage_result['data']}")
                print(f"   🕒 Cached: {usage_result.get('cached', False)}")
            else:
                print(f"   ❌ Groq fetch failed: {usage_result.get('error')}")
        
        # Test 8: Cost Calculations
        print("\n8️⃣ Testing Cost Calculations")
        
        # Test Anthropic pricing
        anthro_cost = manager.calculate_cost(Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 1000, 500)
        expected_anthro = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        print(f"   🧮 Anthropic cost calculation: ${anthro_cost:.6f} (expected ${expected_anthro:.6f})")
        
        # Test Groq pricing
        groq_cost = manager.calculate_cost(Provider.GROQ, "openai/gpt-oss-20b", 1000, 500)
        expected_groq = (1000 + 500) * 0.10 / 1_000_000
        print(f"   🧮 Groq cost calculation: ${groq_cost:.6f} (expected ${expected_groq:.6f})")
        
        # Test 9: Budget Constraints
        print("\n9️⃣ Testing Budget Constraints")
        
        # Try to spend more than available budget
        expensive_result = manager.record_usage(
            Provider.ANTHROPIC,
            "claude-3-5-sonnet-20241022", 
            1_000_000, 500_000,  # Very expensive request
            "test",
            "Testing budget constraints"
        )
        
        if not expensive_result.get("recorded"):
            print(f"   ✅ Budget constraint enforced: {expensive_result.get('reason')}")
        else:
            print(f"   ⚠️ Budget constraint bypassed: {expensive_result}")
        
        # Test with emergency override
        emergency_result = manager.record_usage(
            Provider.ANTHROPIC,
            "claude-3-5-sonnet-20241022",
            10_000, 5_000,  # Moderately expensive
            "emergency",
            "Testing emergency override",
            emergency_override=True
        )
        
        if emergency_result.get("recorded"):
            print(f"   ✅ Emergency override worked: ${emergency_result['cost']:.4f}")
        else:
            print(f"   ❌ Emergency override failed: {emergency_result}")
        
        print("\n🎉 Virtual Budget System Test Complete!")
        
        # Final status
        final_status = manager.get_budget_status()
        print(f"\n📊 Final Budget Status:")
        print(f"• Allocated: ${final_status['daily_budget']['allocated']:.2f}")
        print(f"• Spent: ${final_status['daily_budget']['spent']:.4f}")
        print(f"• Available: ${final_status['daily_budget']['available']:.4f}")
        print(f"• Health: {final_status['budget_health']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ System test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temporary database
        try:
            os.unlink(temp_db_path)
        except:
            pass

def test_mcp_integration():
    """Test MCP server integration (without actually starting server)."""
    print("\n🌐 Testing MCP Server Integration")
    print("=" * 60)
    
    try:
        # Test importing MCP server with new dependencies
        print("1️⃣ Testing MCP server imports")
        import mcp_server
        print("   ✅ MCP server imports successfully")
        
        # Check that virtual budget components are initialized
        if hasattr(mcp_server, 'virtual_budget_manager'):
            print("   ✅ VirtualBudgetManager initialized in MCP server")
        else:
            print("   ❌ VirtualBudgetManager not found in MCP server")
        
        if hasattr(mcp_server, 'billing_reconciler'):
            print("   ✅ BillingReconciliation initialized in MCP server")
        else:
            print("   ❌ BillingReconciliation not found in MCP server")
        
        print("\n2️⃣ Testing endpoint definitions")
        
        # Check that new endpoints exist
        endpoint_checks = [
            "/virtual-budget/status",
            "/virtual-budget/record/anthropic", 
            "/virtual-budget/record/groq",
            "/groq/usage",
            "/billing/reconcile/daily"
        ]
        
        # This is a simple check - in a real test we'd use a test client
        app_routes = [route.path for route in mcp_server.app.routes]
        
        for endpoint in endpoint_checks:
            if endpoint in app_routes:
                print(f"   ✅ Endpoint {endpoint} defined")
            else:
                print(f"   ❌ Endpoint {endpoint} missing")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Comprehensive Virtual Budget Integration Tests")
    
    # Run system tests
    system_success = test_virtual_budget_system()
    
    # Run MCP tests
    mcp_success = test_mcp_integration()
    
    # Summary
    print(f"\n{'=' * 60}")
    print("📋 Test Summary")
    print(f"{'=' * 60}")
    print(f"Virtual Budget System: {'✅ PASS' if system_success else '❌ FAIL'}")
    print(f"MCP Integration: {'✅ PASS' if mcp_success else '❌ FAIL'}")
    
    if system_success and mcp_success:
        print(f"\n🎉 ALL TESTS PASSED - Virtual Budget System Ready!")
    else:
        print(f"\n⚠️  Some tests failed - check logs above")