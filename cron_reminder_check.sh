#!/bin/bash
# Cron script for Mecris intelligent reminder system
# Checks every hour during afternoon (2-5 PM) for walk reminders

# Get the current hour
HOUR=$(date +"%H")

# Only run during afternoon hours (14-17 = 2-5 PM)
if [ "$HOUR" -ge 14 ] && [ "$HOUR" -le 17 ]; then
    echo "$(date): Checking for walk reminders (hour: $HOUR)"
    
    # Call the MCP server trigger endpoint
    RESPONSE=$(curl -s -X POST http://localhost:8000/intelligent-reminder/trigger)
    
    # Log the response
    echo "$(date): Response: $RESPONSE"
    
    # Check if reminder was triggered
    if echo "$RESPONSE" | grep -q '"triggered":true'; then
        echo "$(date): ✅ Reminder sent successfully"
    elif echo "$RESPONSE" | grep -q '"triggered":false'; then
        echo "$(date): ℹ️ No reminder needed"
    else
        echo "$(date): ⚠️ Unexpected response or error"
    fi
else
    echo "$(date): Outside reminder hours (2-5 PM), skipping check"
fi