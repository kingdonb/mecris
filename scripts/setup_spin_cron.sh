#!/bin/bash
# setup_spin_cron.sh
# Sets up the native autonomous failover cron using the Akamai (aka) Spin plugin.

set -e

echo "Setting up Spin AKA Cron for Mecris Failover..."

# Ensure the plugin is installed
spin plugin install aka --yes

echo "Please ensure you are logged in to the Akamai plugin."
echo "If this fails, run: spin aka login"

# Create the cron job
cd mecris-go-spin/sync-service
spin aka cron create \
  --app-name mecris-go-api \
  --path-and-query "/internal/failover-sync" \
  --schedule "0 */2 * * *" \
  --name "failover-cron"

echo "Cron job created successfully!"
