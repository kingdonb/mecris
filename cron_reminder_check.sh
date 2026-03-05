#!/bin/bash
# Cron script for Mecris intelligent reminder system
# Checks every hour during afternoon (2-5 PM) for walk reminders

# Get the current hour
HOUR=$(date +"%H")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Only run during afternoon hours (14-17 = 2-5 PM)
if [ "$HOUR" -ge 14 ] && [ "$HOUR" -le 17 ]; then
    echo "$(date): Checking for walk reminders (hour: $HOUR)"
    
    # Try the MCP server trigger endpoint first
    RESPONSE=$(curl -s -X POST http://localhost:8000/intelligent-reminder/trigger)
    CURL_EXIT=$?
    
    # Log the response
    echo "$(date): MCP Response: $RESPONSE"
    
    # Check if we should fallback to Base Mode (if curl failed, or if there's an error response indicating the server can't handle it due to $0 budget, etc.)
    if [ $CURL_EXIT -ne 0 ] || echo "$RESPONSE" | grep -q '"error":'; then
        echo "$(date): ⚠️ MCP server unavailable or error. Falling back to Base Mode script."
        "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/base_walk_reminder.py"
    else
        # Check if reminder was triggered
        if echo "$RESPONSE" | grep -q '"triggered":true'; then
            echo "$(date): ✅ Reminder sent successfully via MCP"
        elif echo "$RESPONSE" | grep -q '"triggered":false'; then
            echo "$(date): ℹ️ No reminder needed (MCP)"
        else
            echo "$(date): ⚠️ Unexpected response format. Attempting fallback."
            "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/base_walk_reminder.py"
        fi
    fi
else
    echo "$(date): Outside reminder hours (2-5 PM), skipping check"
fi