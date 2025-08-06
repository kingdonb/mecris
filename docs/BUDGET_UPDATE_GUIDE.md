# Budget Update Guide

> **Simple instructions for keeping Mecris budget tracking accurate**

## What Mecris Tracks Automatically

Mecris keeps track of your Claude API usage locally like a **checkbook**:

- **Token usage** from every Claude session (input/output tokens)
- **Estimated costs** based on current Anthropic pricing  
- **Remaining budget** calculated from your last known balance
- **Daily burn rate** and projected spend until expiration

**Think of it as writing checks** - Mecris estimates what you're spending, but the bank (Anthropic) has the real balance.

## When You Need to Update

Update your budget when you check your actual credit balance in the Anthropic Console:

1. **Daily or weekly** - for accurate budget tracking
2. **When you get a billing notification** from Anthropic
3. **Before important work** - to know your real remaining credits
4. **When Mecris warnings seem off** - reconcile estimated vs. actual

## How to Update (Simple Method)

### Step 1: Check Your Anthropic Console Balance
1. Go to https://console.anthropic.com/settings/billing
2. Note your **remaining credits** (e.g., `$13.92`)
3. Note your **total credits** for this period (e.g., `$24.02`)

### Step 2: Run the Update Script
```bash
./update_budget.sh 13.92 24.02
```

**Format:** `./update_budget.sh <remaining> <total>`

### Step 3: Verify the Update
The script will show your updated budget status. Claude will now see the correct balance in its context.

## Budget Update Script

Create this script in your Mecris directory:

**`update_budget.sh`**
```bash
#!/bin/bash
# Budget update script - keeps Mecris tracking accurate

REMAINING=${1}
TOTAL=${2}
PERIOD_END="2025-08-05"  # Update this for your billing period

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
```

Make it executable: `chmod +x update_budget.sh`

## What Happens During Update

1. **Mecris reconciles** your estimated spending with Anthropic's actual billing
2. **Discrepancies are absorbed** - Mecris adjusts its local tracking
3. **Future estimates continue** from the new known balance
4. **Claude gets updated context** - sees real remaining budget, not estimates

## Security Note

This approach **keeps your Anthropic credentials secure**:
- ✅ You manually check the console (no stored passwords)
- ✅ Simple script updates local tracking only
- ✅ No violation of Anthropic's terms of service
- ✅ You maintain full control of your account

## Troubleshooting

**Script fails?**
```bash
# Make sure Mecris server is running
./scripts/launch_server.sh

# Check server health
curl -s http://localhost:8000/health
```

**Budget looks wrong?**
- Double-check the values from Anthropic Console
- Run the script again with correct values
- The `used_budget` will adjust automatically

**Claude giving budget warnings?**
Check if your period end date is correct in the script.

---

**Remember:** Mecris estimates between your updates, Anthropic has the real numbers. Update regularly to keep Claude informed and avoid surprises!