#!/bin/bash
set -e

MODEL="claude-haiku-4.5"
PROVIDER="github-copilot"
EXTENSION="./.pi/extensions/mecris/index.ts"
PASS=0
FAIL=0

test_case() {
  local name="$1"
  local prompt="$2"
  
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Test: $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  if pi -e "$EXTENSION" --model "$MODEL" --provider "$PROVIDER" --no-session -p "$prompt" 2>&1; then
    PASS=$((PASS + 1))
    echo "✅ PASS: $name"
  else
    FAIL=$((FAIL + 1))
    echo "❌ FAIL: $name"
  fi
}

echo ""
echo "════════════════════════════════════════════════════════════"
echo "E2E Test Suite: Pi + Mecris Bridge"
echo "════════════════════════════════════════════════════════════"
echo "Model: $MODEL | Provider: $PROVIDER"
echo "Extension: $EXTENSION"
echo ""

# Core tool tests
test_case "Core 1: mecris_get_narrator_context" \
  "Call mecris_get_narrator_context. Summarize: (1) budget days left, (2) daily score (e.g. 1/3), (3) any urgent items."

test_case "Core 2: mecris_get_beeminder_status" \
  "Call mecris_get_beeminder_status. Count and report how many goals are SAFE vs at-risk."

test_case "Core 3: mecris_get_budget_status" \
  "Call mecris_get_budget_status. Report: (1) health status (GOOD/LOW/CRITICAL), (2) days remaining, (3) daily burn rate."

test_case "Core 4: mecris_get_daily_aggregate_status" \
  "Call mecris_get_daily_aggregate_status. Report the score (e.g., 1/3 or 2/3) and which daily goals are met."

test_case "Core 5: mecris_get_system_health" \
  "Call mecris_get_system_health. List the status of each system component (MCP, Android, cloud, etc.)."

# Deferred tool tests
test_case "Deferred: Load and use usage tools" \
  "Use mecris_load_tools to activate tools for usage/recording. Then call mecris_get_recent_usage and report how many sessions exist."

test_case "Deferred: Load and query bookmarks" \
  "Use mecris_load_tools to activate bookmark tools. Then describe what bookmarks exist (don't need to call if tool desc is enough)."

echo ""
echo "════════════════════════════════════════════════════════════"
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
  echo "🎉 All tests passed!"
  echo "════════════════════════════════════════════════════════════"
  exit 0
else
  echo "⚠️  Some tests failed. Review output above."
  echo "════════════════════════════════════════════════════════════"
  exit 1
fi
