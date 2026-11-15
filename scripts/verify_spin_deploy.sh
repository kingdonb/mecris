#!/usr/bin/env bash
# verify_spin_deploy.sh
# Post-deploy check for the Spin sync service (kingdonb/mecris#183, #369).
# It sends no WhatsApp message unless asked to.
#
# It tests as the callers do, not as a person with curl and a header would:
#   - waits until the live service reports the version in spin.toml
#     (a deploy command returning is not a deploy being live)
#   - sends no keyed request at all unless /version matches, /version promises a dry run
#     ("dry_run": true) and the burned-key refusals below are counted: a v0.2 handler
#     ignores ?dry_run=1 and would run the real reminder loop
#   - no key, a wrong key and both forms of the old published key are refused,
#     and the burned-key refusals are counted in internal_refusals
#   - every key it presents is the real one, the burned one or marked with the
#     verify-probe- prefix (outcome.rs VERIFY_PROBE_PREFIX, not a secret). Spin counts a
#     marked key as reason 'probe', never 'bad_key', so this check raises no narrator alert
#   - an unsigned or forged Twilio webhook post is refused
#   - a dry run of trigger-reminders (sends and writes nothing) shows New York time
#     and a verdict for every user
#   - a cron-shaped failover-sync request (GET, key in the query, no headers, which is
#     exactly what Akamai cron sends) is accepted and leaves a fresh akamai_functions
#     heartbeat and a last_status in scheduler_election
#
# The private key never appears on a command line: curl reads the URL from stdin (-K -).
# Neon is read with a read-only session: counts and the last_status line, nothing else.
#
# Usage: ./scripts/verify_spin_deploy.sh [--live-trigger]
#   --live-trigger  also send a real cron-shaped trigger-reminders request. Inside the
#                   reminder window this can send a WhatsApp message.
#   SPIN_BASE_URL overrides the service URL, MECRIS_ENV_FILE the .env file, and
#   MECRIS_PYTHON the interpreter (with psycopg2) used for the read-only Neon checks.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${SPIN_BASE_URL:-https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app}"
ENV_FILE="${MECRIS_ENV_FILE:-$PROJECT_ROOT/.env}"
PY="${MECRIS_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
LIVE_TRIGGER=0
for arg in "$@"; do
    case "$arg" in
        --live-trigger) LIVE_TRIGGER=1 ;;
        --no-trigger) ;;  # the old opt-out; the dry run is now the default
        *) echo "Usage: $0 [--live-trigger]" >&2; exit 2 ;;
    esac
done

env_value() { grep "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"; }
KEY="$(env_value INTERNAL_API_KEY)"
if [[ -z "$KEY" ]]; then echo "ERROR: INTERNAL_API_KEY not found in $ENV_FILE" >&2; exit 2; fi
NEON_DB_URL="$(env_value NEON_DB_URL)"
export NEON_DB_URL
EXPECTED="$(sed -n 's/^version = "\(.*\)"/\1/p' "$PROJECT_ROOT/mecris-go-spin/sync-service/spin.toml" | head -1)"

failures=0
status() { curl -s -o /dev/null -w '%{http_code}' -m 30 "$@"; }
check() {  # check <description> <expected> <actual>
    if [[ "$3" == "$2" ]]; then echo "  ok    $1 ($3)"; else echo "  FAIL  $1: expected $2, got $3"; failures=$((failures + 1)); fi
}
fail() { echo "  FAIL  $1"; failures=$((failures + 1)); }

# keyed <path-and-query>: GET with the private key in the query, as Akamai cron sends it.
# Prints the body, a newline and the status code. The URL reaches curl on stdin only.
keyed() {
    local sep='?'
    [[ "$1" == *\?* ]] && sep='&'
    printf 'url = "%s%s%skey=%s"\n' "$BASE" "$1" "$sep" "$KEY" | curl -s -m 120 -w $'\n%{http_code}' -K -
}

# neon <query> [args]: one value from Neon, read-only. Queries are fixed; args are bound.
neon() {
    "$PY" - "$@" <<'PY'
import os, sys
import psycopg2
queries = {
    "now": ("SELECT FLOOR(EXTRACT(EPOCH FROM now()))::BIGINT", 0),
    "refusals": ("SELECT COALESCE(SUM(count), 0) FROM internal_refusals WHERE day = (now() AT TIME ZONE 'America/New_York')::DATE AND endpoint = %s AND reason = %s", 2),
    # A /health call bumps heartbeat but keeps the old last_status, so the sync segment's own
    # HH:MMZ stamp must be t0's minute or up to 30 minutes after it (modulo a UTC midnight).
    "cron_rows_since": ("SELECT COUNT(*) FROM (SELECT heartbeat, substring(last_status from 'sync ([0-9][0-9]:[0-9][0-9])Z') AS seg, to_timestamp(%s) AS t0 FROM scheduler_election WHERE role = 'akamai_functions' AND intent = 'cron') s WHERE s.heartbeat >= s.t0 AND s.seg IS NOT NULL AND MOD(FLOOR(EXTRACT(EPOCH FROM s.seg::TIME - date_trunc('minute', s.t0 AT TIME ZONE 'UTC')::TIME) / 60)::BIGINT + 1440, 1440) <= 30", 1),
    "last_status": ("SELECT COALESCE(last_status, '') FROM scheduler_election WHERE role = 'akamai_functions' ORDER BY heartbeat DESC LIMIT 1", 0),
}
name, args = sys.argv[1], sys.argv[2:]
sql, nargs = queries[name]
if len(args) != nargs:
    sys.exit(f"{name} takes {nargs} argument(s)")
conn = psycopg2.connect(os.environ["NEON_DB_URL"])
conn.set_session(readonly=True)
try:
    with conn.cursor() as cur:
        cur.execute(sql, args or None)
        row = cur.fetchone()
        print("" if row is None or row[0] is None else row[0])
finally:
    conn.close()
PY
}

# stop <reason>: refuse to send any keyed request. A v0.2 trigger-reminders handler ignores
# ?dry_run=1 and runs the real reminder loop, so a keyed request is only safe once the
# service has shown it is v0.3.
stop() {
    fail "$1"
    echo "Stopped before any keyed request: the service has not shown that it honours ?dry_run=1."
    echo "$failures check(s) failed."
    exit 1
}

echo "Service: $BASE"
echo "Waiting for version $EXPECTED to be live..."
live=""
version_json=""
for _ in $(seq 1 50); do
    version_json="$(curl -s -m 15 "$BASE/version")"
    live="$(printf '%s' "$version_json" | sed -n 's/.*"version": *"\([^"]*\)".*/\1/p')"
    [[ "$live" == "$EXPECTED" ]] && break
    sleep 6
done
if [[ "$live" == "$EXPECTED" ]]; then echo "  ok    version $live is serving"
else stop "live version is '${live:-unknown}', expected $EXPECTED"; fi
# The version string may not have been bumped yet (v0.2 also said 0.2.0): require the promise.
if [[ "$version_json" =~ \"dry_run\":\ *true ]]; then echo "  ok    /version promises a dry run"
else stop "/version does not promise a dry run (\"dry_run\": true): an older handler would send for real"; fi

neon_ok=1
if [[ -z "$NEON_DB_URL" ]]; then neon_ok=0; fail "NEON_DB_URL not found in $ENV_FILE: the database checks cannot run"; fi
# A wrong key marked as this script's probe: refused, counted as 'probe', never 'bad_key'
# (a bad_key refusal raises an urgent narrator item for the rest of the New York day).
PROBE_KEY="verify-probe-not-the-key"
burned_before=""
probe_before=""
if [[ "$neon_ok" == 1 ]]; then
    burned_before="$(neon refusals trigger-reminders burned_key)"
    probe_before="$(neon refusals trigger-reminders probe)"
fi

echo "Internal endpoints refuse callers without the private key:"
check "trigger-reminders, no key" 401 "$(status "$BASE/internal/trigger-reminders")"
check "trigger-reminders, wrong key (marked as a probe)" 401 "$(status "$BASE/internal/trigger-reminders?key=$PROBE_KEY")"
check "trigger-reminders, old published key in header" 401 "$(status -H 'x-internal-api-key: test-internal-key' "$BASE/internal/trigger-reminders")"
check "trigger-reminders, old published key in query" 401 "$(status "$BASE/internal/trigger-reminders?key=test-internal-key")"
check "failover-sync, no key" 401 "$(status "$BASE/internal/failover-sync")"

echo "Twilio webhook refuses unsigned requests:"
check "webhook, no signature" 403 "$(status -X POST -d 'Body=YES&From=%2B15005550006' "$BASE/internal/twilio-webhook")"
check "webhook, forged signature" 403 "$(status -X POST -H 'X-Twilio-Signature: AAAAAAAAAAAAAAAAAAAAAAAAAAA=' -d 'Body=YES&From=%2B15005550006' "$BASE/internal/twilio-webhook")"

if [[ "$neon_ok" == 1 ]]; then
    burned_after="$(neon refusals trigger-reminders burned_key)"
    if [[ "$burned_before" =~ ^[0-9]+$ && "$burned_after" =~ ^[0-9]+$ ]] && (( burned_after >= burned_before + 2 )); then
        echo "  ok    burned-key refusals counted in internal_refusals ($burned_before -> $burned_after today)"
    else
        # Only v0.3 counts refusals: an older service may still be answering.
        stop "burned-key refusals not counted in internal_refusals ('$burned_before' -> '$burned_after')"
    fi
    probe_after="$(neon refusals trigger-reminders probe)"
    if [[ "$probe_before" =~ ^[0-9]+$ && "$probe_after" =~ ^[0-9]+$ ]] && (( probe_after >= probe_before + 1 )); then
        echo "  ok    wrong-key probe counted as 'probe', not 'bad_key' ($probe_before -> $probe_after today)"
    else
        fail "wrong-key probe not counted as 'probe' ('$probe_before' -> '$probe_after'): it may have raised a bad_key alert"
    fi
fi

echo "Dry run of trigger-reminders (sends nothing, writes nothing):"
body="$(keyed "/internal/trigger-reminders?dry_run=1")"
check "trigger-reminders dry run" 200 "${body##*$'\n'}"
summary="$(printf '%s' "${body%$'\n'*}" | "$PY" -c '
import json, re, sys
d = json.load(sys.stdin)
assert d.get("dry_run") is True, "not a dry run"
users = d.get("users") or []
for u in users:
    assert re.search(r" E[SD]T$", u.get("ny_time", "")), "ny_time is not America/New_York"
    assert u.get("verdict") and u.get("reason"), "missing verdict"
    print("        %s: %s (%s) at %s, America/New_York" % (u.get("familiar_id") or "(no familiar_id)", u["verdict"], u["reason"], u["ny_time"]))
print("        %d user(s)" % len(users))
' 2>&1)"
if [[ $? -eq 0 ]]; then echo "$summary"; echo "  ok    dry run reports New York time and a verdict per user"
else fail "dry run response: $summary"; fi

echo "A cron-shaped failover-sync request is accepted and recorded:"
if [[ "$neon_ok" == 1 ]]; then t0="$(neon now)"; fi
body="$(keyed "/internal/failover-sync")"
check "failover-sync as cron" 200 "${body##*$'\n'}"
echo "        response: ${body%$'\n'*}"
if [[ "$neon_ok" == 1 ]]; then
    rows="$(neon cron_rows_since "$t0")"
    if [[ "$rows" =~ ^[0-9]+$ ]] && (( rows >= 1 )); then echo "  ok    akamai_functions row with a sync outcome stamped after the request"
    else fail "no akamai_functions row with a sync outcome stamped after the request ('$rows')"; fi
    last="$(neon last_status)"
    if [[ "$last" == *"sync "* ]]; then echo "  ok    last_status: $last"
    else fail "last_status has no sync outcome: '$last'"; fi
fi

if [[ "$LIVE_TRIGGER" == 1 ]]; then
    echo "A real cron-shaped trigger-reminders request (--live-trigger):"
    body="$(keyed "/internal/trigger-reminders")"
    check "trigger-reminders as cron" 200 "${body##*$'\n'}"
    echo "        response: ${body%$'\n'*}"
else
    echo "Skipped the real trigger-reminders request (pass --live-trigger to send one)."
fi

if [[ "$failures" -gt 0 ]]; then echo "$failures check(s) failed."; exit 1; fi
echo "All checks passed."
