#!/usr/bin/env python3
"""
MCP Budget Reconciliation Script

Replaces scripts/update_budget.sh with proper reconciliation tracking.
This script maintains the accurate budget tracking while adding audit trail
for manual adjustments (the "ghost usage" problem).

Usage:
    python mcp_reconcile_budget.py <remaining_budget> [total_budget]
    python mcp_reconcile_budget.py 19.54 24.96
"""
import sys
import requests
import json
import argparse
from datetime import datetime

MCP_BASE_URL = "http://localhost:8000"

def get_current_budget_status():
    """Get current budget status from MCP"""
    try:
        response = requests.get(f"{MCP_BASE_URL}/usage")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get current budget status: {e}")
        sys.exit(1)

def record_reconciliation(current_budget: float, manual_adjustment: float, reason: str):
    """Record budget reconciliation through MCP"""
    try:
        data = {
            "current_budget": current_budget,
            "manual_adjustment": manual_adjustment, 
            "adjustment_reason": reason
        }
        response = requests.post(f"{MCP_BASE_URL}/budget/reconcile", json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to record reconciliation: {e}")
        sys.exit(1)

def update_budget_directly(remaining: float, total: float = None, period_end: str = "2025-09-30"):
    """Update budget through existing endpoint (for comparison)"""
    try:
        params = {"remaining_budget": remaining}
        if total:
            params["total_budget"] = total
        params["period_end"] = period_end
        
        response = requests.post(f"{MCP_BASE_URL}/usage/update_budget", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to update budget: {e}")
        sys.exit(1)

def get_reconciliation_status():
    """Get reconciliation status and recommendations"""
    try:
        response = requests.get(f"{MCP_BASE_URL}/budget/reconciliation/status")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️ Could not get reconciliation status: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Reconcile Claude budget with proper audit tracking",
        epilog="Example: python mcp_reconcile_budget.py 19.54 24.96"
    )
    parser.add_argument("remaining", type=float, 
                       help="Current remaining budget from Anthropic Console")
    parser.add_argument("total", type=float, nargs="?",
                       help="Total budget (optional, updates period total)")
    parser.add_argument("--reason", default="anthropic-console-sync",
                       help="Reason for reconciliation (default: anthropic-console-sync)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without making changes")
    
    args = parser.parse_args()
    
    print("🔄 MCP Budget Reconciliation")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get current status
    print("📊 Getting current budget status...")
    current_status = get_current_budget_status()
    tracked_remaining = current_status["remaining_budget"]
    tracked_total = current_status["total_budget"]
    
    # Calculate adjustment needed
    manual_adjustment = args.remaining - tracked_remaining
    
    print(f"💰 Budget Comparison:")
    print(f"   Tracked remaining:  ${tracked_remaining:.2f}")
    print(f"   Actual remaining:   ${args.remaining:.2f}")
    print(f"   Manual adjustment:  ${manual_adjustment:+.2f}")
    
    if args.total:
        print(f"   Total budget:       ${args.total:.2f}")
    print()
    
    # Show what will happen
    if abs(manual_adjustment) < 0.01:
        print("✅ Budget is already in sync - no adjustment needed")
        sys.exit(0)
    
    if manual_adjustment > 0:
        print(f"⬆️ Budget will be INCREASED by ${manual_adjustment:.2f}")
        print("   (Provider returned credits or error in tracking)")
    else:
        print(f"⬇️ Budget will be DECREASED by ${abs(manual_adjustment):.2f}")
        print("   (Real usage not captured by session tracking)")
    
    print(f"📝 Adjustment reason: {args.reason}")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN - No changes made")
        sys.exit(0)
    
    # Confirm before making changes
    if abs(manual_adjustment) > 5.0:
        confirm = input(f"⚠️ Large adjustment (${abs(manual_adjustment):.2f}). Continue? [y/N]: ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            sys.exit(1)
    
    # Record reconciliation with proper tracking
    print("📋 Recording reconciliation...")
    reconciliation_result = record_reconciliation(
        current_budget=args.remaining,
        manual_adjustment=manual_adjustment,
        reason=args.reason
    )
    
    if reconciliation_result["success"]:
        print("✅ Reconciliation recorded successfully")
        
        # Show updated status
        updated_status = get_current_budget_status()
        print()
        print("📈 Updated Budget Status:")
        print(f"   Remaining:      ${updated_status['remaining_budget']:.2f}")
        print(f"   Total:          ${updated_status['total_budget']:.2f}")
        print(f"   Used:           ${updated_status['used_budget']:.2f}")
        print(f"   Days remaining: {updated_status['days_remaining']}")
        print(f"   Health:         {updated_status['budget_health']}")
        
        # Show reconciliation status
        recon_status = get_reconciliation_status()
        if recon_status and recon_status.get("success"):
            period_summary = recon_status.get("period_summary", {})
            print()
            print("🔍 Reconciliation Summary:")
            print(f"   This period reconciliations: {period_summary.get('reconciliation_count', 0)}")
            print(f"   Total adjustments: ${period_summary.get('total_adjustments', 0):.2f}")
            print(f"   Tracking health: {recon_status.get('budget_tracking_health', 'UNKNOWN')}")
        
    else:
        print("❌ Reconciliation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()