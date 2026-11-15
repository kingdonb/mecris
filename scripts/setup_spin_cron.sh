#!/usr/bin/env bash
# setup_spin_cron.sh
# (Re)creates the Akamai platform cron jobs for the Mecris sync service.
#
# Akamai cron can only set the request path and query string, never headers, so
# the internal key travels as the `key` query parameter. Rotating INTERNAL_API_KEY
# therefore means: redeploy (deploy-akamai.sh), then rerun this script.
#
# Usage: ./scripts/setup_spin_cron.sh
# The jobs it creates (v0.3.0):
#   trigger-reminders   0 */2 * * *   walk reminder gates; WhatsApp only as the fallback
#   failover-sync       5 */2 * * *   cloud-owned Clozemaster sync; skips stats under 100 min old
# Delete the old jobs of the same names first (spin aka cron delete <name>). Upgrading
# from v0.2.0 also means deleting the two daily jobs this replaces:
#   spin aka cron delete failover-sync-edt
#   spin aka cron delete failover-sync-est
# The app is the one linked to mecris-go-spin/sync-service (mecris-sync-v2), so no
# --app-name is passed.

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
spin aka cron list || { echo "Run: spin aka login" >&2; exit 1; }

spin aka cron create \
  --path-and-query "/internal/trigger-reminders?key=${INTERNAL_API_KEY}" \
  --schedule "0 */2 * * *" \
  --name "trigger-reminders"

spin aka cron create \
  --path-and-query "/internal/failover-sync?key=${INTERNAL_API_KEY}" \
  --schedule "5 */2 * * *" \
  --name "failover-sync"

echo "Done. Verify with: spin aka cron list (it prints the key; do not paste its output anywhere)"
