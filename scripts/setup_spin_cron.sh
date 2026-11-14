#!/usr/bin/env bash
# setup_spin_cron.sh
# (Re)creates the Akamai platform cron jobs for the Mecris sync service.
#
# Akamai cron can only set the request path and query string, never headers, so
# the internal key travels as the `key` query parameter. Rotating INTERNAL_API_KEY
# therefore means: redeploy (deploy-akamai.sh), then rerun this script.
#
# Usage: ./scripts/setup_spin_cron.sh
# The jobs it creates match what `spin aka cron list` showed on 2026-11-13:
#   trigger-reminders   0 */2 * * *
#   failover-sync-edt   5 4 * * *
#   failover-sync-est   5 5 * * *
# Delete the old jobs of the same names first (spin aka cron delete <name>).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; source "$PROJECT_ROOT/.env"; set +a

if [[ -z "${INTERNAL_API_KEY:-}" || "$INTERNAL_API_KEY" == "test-internal-key" || ${#INTERNAL_API_KEY} -lt 32 ]]; then
    echo "ERROR: INTERNAL_API_KEY must be a private random value of 32+ characters (openssl rand -hex 32)" >&2
    exit 1
fi
if [[ ! "$INTERNAL_API_KEY" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: INTERNAL_API_KEY must be URL-safe (letters, digits, - and _) to be used in a cron query string" >&2
    exit 1
fi

cd "$PROJECT_ROOT/mecris-go-spin/sync-service"

echo "Existing cron jobs (delete stale ones with: spin aka cron delete <name>):"
spin aka cron list --app-name mecris-go-api || { echo "Run: spin aka login" >&2; exit 1; }

spin aka cron create \
  --app-name mecris-go-api \
  --path-and-query "/internal/trigger-reminders?key=${INTERNAL_API_KEY}" \
  --schedule "0 */2 * * *" \
  --name "trigger-reminders"

spin aka cron create \
  --app-name mecris-go-api \
  --path-and-query "/internal/failover-sync?key=${INTERNAL_API_KEY}" \
  --schedule "5 4 * * *" \
  --name "failover-sync-edt"

spin aka cron create \
  --app-name mecris-go-api \
  --path-and-query "/internal/failover-sync?key=${INTERNAL_API_KEY}" \
  --schedule "5 5 * * *" \
  --name "failover-sync-est"

echo "Done. Verify with: spin aka cron list --app-name mecris-go-api"
