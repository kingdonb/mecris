#!/usr/bin/env bash
# verify_spin_deploy.sh
# Post-deploy check for the Spin sync service (kingdonb/mecris#183).
#
# It tests as the callers do, not as a person with curl and a header would:
#   - waits until the live service reports the version in spin.toml
#     (a deploy command returning is not a deploy being live)
#   - no key, and the old published key, must be refused
#   - an unsigned or forged Twilio webhook post must be refused
#   - a GET with the key in the query string and NO headers, which is exactly
#     what Akamai cron sends, must be accepted
#
# The last check really runs the reminder logic. Pass --no-trigger to skip it.
# The key is read from .env and never printed.
#
# Usage: ./scripts/verify_spin_deploy.sh [--no-trigger]
#   SPIN_BASE_URL overrides the service URL.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${SPIN_BASE_URL:-https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app}"
TRIGGER=1
[[ "${1:-}" == "--no-trigger" ]] && TRIGGER=0

KEY="$(grep '^INTERNAL_API_KEY=' "$PROJECT_ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
if [[ -z "$KEY" ]]; then echo "ERROR: INTERNAL_API_KEY not found in .env" >&2; exit 2; fi
EXPECTED="$(sed -n 's/^version = "\(.*\)"/\1/p' "$PROJECT_ROOT/mecris-go-spin/sync-service/spin.toml" | head -1)"

failures=0
status() { curl -s -o /dev/null -w '%{http_code}' -m 30 "$@"; }
check() {  # check <description> <expected status> <actual status>
    if [[ "$3" == "$2" ]]; then echo "  ok    $1 ($3)"; else echo "  FAIL  $1: expected $2, got $3"; failures=$((failures + 1)); fi
}

echo "Service: $BASE"
echo "Waiting for version $EXPECTED to be live..."
live=""
for _ in $(seq 1 50); do
    live="$(curl -s -m 15 "$BASE/version" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')"
    [[ "$live" == "$EXPECTED" ]] && break
    sleep 6
done
if [[ "$live" == "$EXPECTED" ]]; then echo "  ok    version $live is serving"
else echo "  FAIL  live version is '${live:-unknown}', expected $EXPECTED"; failures=$((failures + 1)); fi

echo "Internal endpoints refuse callers without the private key:"
check "trigger-reminders, no key" 401 "$(status "$BASE/internal/trigger-reminders")"
check "trigger-reminders, old published key in header" 401 "$(status -H 'x-internal-api-key: test-internal-key' "$BASE/internal/trigger-reminders")"
check "trigger-reminders, old published key in query" 401 "$(status "$BASE/internal/trigger-reminders?key=test-internal-key")"
check "failover-sync, no key" 401 "$(status "$BASE/internal/failover-sync")"

echo "Twilio webhook refuses unsigned requests:"
check "webhook, no signature" 403 "$(status -X POST -d 'Body=YES&From=%2B15005550006' "$BASE/internal/twilio-webhook")"
check "webhook, forged signature" 403 "$(status -X POST -H 'X-Twilio-Signature: AAAAAAAAAAAAAAAAAAAAAAAAAAA=' -d 'Body=YES&From=%2B15005550006' "$BASE/internal/twilio-webhook")"

if [[ "$TRIGGER" == 1 ]]; then
    echo "A cron-shaped request (GET, key in query, no headers) is accepted:"
    body="$(curl -s -m 90 -w $'\n%{http_code}' "$BASE/internal/trigger-reminders?key=$KEY")"
    check "trigger-reminders as cron" 200 "${body##*$'\n'}"
    echo "        response: ${body%$'\n'*}"
else
    echo "Skipped the cron-shaped request (--no-trigger)."
fi

if [[ "$failures" -gt 0 ]]; then echo "$failures check(s) failed."; exit 1; fi
echo "All checks passed."
