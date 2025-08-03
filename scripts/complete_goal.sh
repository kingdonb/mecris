#!/bin/bash
# Goal completion script - check off goals in Mecris

GOAL_ID=${1}

if [ -z "$GOAL_ID" ]; then
    echo "Usage: $0 <goal_id>"
    echo ""
    echo "Available goals:"
    curl -s http://localhost:8000/goals | jq -r '.goals[] | "\(.id): \(.title) [\(.priority)] - \(.status)"'
    exit 1
fi

echo "Completing goal $GOAL_ID..."

# Complete the goal
RESPONSE=$(curl -s -X POST "http://localhost:8000/goals/$GOAL_ID/complete")

if echo "$RESPONSE" | jq -e '.completed' > /dev/null 2>&1; then
    echo "✅ Goal completed successfully!"
    echo "$RESPONSE" | jq '{title, completed_at}'
else
    echo "❌ Failed to complete goal:"
    echo "$RESPONSE" | jq .
    exit 1
fi

echo -e "\nRemaining active goals:"
curl -s http://localhost:8000/goals | jq -r '.goals[] | select(.status == "active") | "\(.id): \(.title) [\(.priority)]"'