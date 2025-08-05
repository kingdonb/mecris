#!/bin/bash
# Setup cron job for Mecris walk reminders
# Run this script to install the hourly reminder check

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/cron_reminder_check.sh"
LOG_FILE="$SCRIPT_DIR/logs/reminder_cron.log"

echo "Setting up Mecris walk reminder cron job..."

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Create cron entry (runs every hour, but script filters to 2-5 PM)
CRON_ENTRY="0 * * * * $CRON_SCRIPT >> $LOG_FILE 2>&1"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "cron_reminder_check.sh"; then
    echo "⚠️ Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "cron_reminder_check.sh" | crontab -
fi

# Add new cron entry
echo "Installing new cron job..."
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job installed successfully!"
echo ""
echo "The system will now check for walk reminders every hour from 2-5 PM."
echo "Logs will be written to: $LOG_FILE"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To remove this cron job: crontab -l | grep -v cron_reminder_check.sh | crontab -"
echo ""
echo "Manual test: $CRON_SCRIPT"