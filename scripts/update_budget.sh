#!/bin/bash
# Budget update script - keeps Mecris tracking accurate

REMAINING=${1}
TOTAL=${2}
PERIOD_END="2025-09-30"  # Update this for your billing period

if [ -z "$REMAINING" ]; then
    echo "Usage: $0 <remaining_credits> [total_credits]"
    echo "Example: $0 13.92 24.02"
    echo ""
    echo "Get these values from: https://console.anthropic.com/settings/billing"
    exit 1
fi

echo "Updating budget: $REMAINING remaining${TOTAL:+ of $TOTAL total}..."

if [ -n "$TOTAL" ]; then
    # Update both total and remaining
    curl -s -X POST "http://localhost:8000/usage/update_budget?remaining_budget=$REMAINING&total_budget=$TOTAL&period_end=$PERIOD_END" | jq .
else
    # Update remaining only
    curl -s -X POST "http://localhost:8000/usage/update_budget?remaining_budget=$REMAINING" | jq .
fi

echo -e "\nCurrent budget status:"
curl -s http://localhost:8000/usage | jq '{remaining_budget, total_budget, used_budget, days_remaining, budget_health}'
