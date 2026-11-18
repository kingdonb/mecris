# Mecris-Go Backend Deployment

**Canonical target: Akamai Functions (edge) at `https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app`**

### Cloud Architecture & Status
- **Akamai Functions (`fwf.app`)**: **ACTIVE & AUTHORITATIVE**. Fully operational with Neon Postgres, encrypted Twilio tokens, and pre-approved WhatsApp Utility Templates.
- **Fermyon Cloud (`fermyon.app`)**: **INACTIVE**. Multi-tenant runtime fails during WASM instantiation (`failed to prepare your Spin application`) due to capability/socket boundaries in their shared environment. All Fermyon deployments have been cleanly deprovisioned to prevent dangling broken endpoints.

---

## One-Command Cloud Deployments

### 1. Akamai Functions (Edge — Primary)
```bash
cd mecris-go-spin/sync-service
./deploy-akamai.sh
```

### 2. Fermyon Cloud (Inactive)
Fermyon Cloud is inactive (see above), so there is nothing to deploy there. `deploy-akamai.sh` is the only deployment script to run. `deploy-fermyon.sh` is kept in the tree for reference only.

`deploy-akamai.sh`:
1. Load secrets from the project root `.env` (gitignored, local only)
2. Validate all required variables are present
3. Encrypt the Twilio auth token using the master encryption key
4. Fetch the Pocket ID JWKS from the private network (Tailscale/home LAN)
5. Inject the pre-approved WhatsApp Utility Template SID (`TWILIO_WHATSAPP_TEMPLATE_SID`)
6. Deploy with ALL variables in a single atomic command in **Production WhatsApp Delivery Mode**

**No manual variable setting, no dashboard clicks, no missed secrets.**

---

## Required Environment Variables (in project root `.env`)

| Variable | Source | Purpose |
|----------|--------|---------|
| `NEON_DB_URL` | Neon Console | PostgreSQL connection string |
| `MASTER_ENCRYPTION_KEY` | Generate once: `openssl rand -hex 32` | AES-256-GCM key for encrypting secrets |
| `CLOZEMASTER_EMAIL` | Clozemaster account | Autonomous language sync |
| `CLOZEMASTER_PASSWORD` | Clozemaster account | Autonomous language sync |
| `TWILIO_ACCOUNT_SID` | Twilio Console | WhatsApp & alert notifications |
| `TWILIO_AUTH_TOKEN` | Twilio Console | WhatsApp notifications (plaintext in .env, encrypted at deploy) |
| `TWILIO_WHATSAPP_TEMPLATE_SID` | Meta / Twilio Console | Pre-approved Utility Template SID (default: `HX638b7f9403e04c8fa880370f1b7a9ba1`) |
| `OPENWEATHER_API_KEY` | OpenWeatherMap | Weather heuristic for walk reminders |
| `TWILIO_WHATSAPP_FROM` | Twilio Console (WhatsApp sender) | Sender for the sync service's WhatsApp templates, e.g. `whatsapp:+1...`. Required: SMS is disabled and there is no fallback. |
| `TWILIO_STATUS_TEMPLATE_SID` | Meta / Twilio Console | `mecris_status_v2`, used for walk reminders and verification codes (default: `HX9403f1b85350b8c05780a1128b79f3c2`) |
| `INTERNAL_API_KEY` | `openssl rand -hex 32` | Guards `/internal/trigger-reminders` and `/internal/failover-sync`. Private, 32+ URL-safe characters. |
| `TWILIO_STATUS_CALLBACK_URL` | Optional, e.g. `https://<app host>/internal/twilio-status` | Becomes the Spin variable `twilio_status_callback_url`. Set: every WhatsApp send asks Twilio for status callbacks at this URL, and their signatures are checked against it. Unset: no StatusCallback is sent; the SID is still recorded. |

### Internal endpoints and platform cron
`/internal/trigger-reminders` and `/internal/failover-sync` accept only the internal cron key (v0.3.0). A signed-in user's bearer token is refused: the phone no longer calls them, and one user must not start the all-users loop. The key may be sent as the `x-internal-api-key` header or as the `key` query parameter. Akamai cron can only set path and query, so cron jobs use the query form; `scripts/setup_spin_cron.sh` creates them (`trigger-reminders` at `0 */2 * * *`, `failover-sync` at `5 */2 * * *`). An unset key authorizes nobody, and the service refuses the old published value `test-internal-key`. After rotating the key: redeploy, then recreate the cron jobs.

#### What the key can do (blast radius)

The key opens exactly two routes. It cannot deploy, change variables, read secrets, or reach any paid model API (Helix, Anthropic, OpenRouter, Groq).

| Route | With the key, a caller can | Bounded by |
|---|---|---|
| `/internal/trigger-reminders` | Run the all-users walk reminder loop, which may send a WhatsApp template through Twilio (cents per message). With `?dry_run=1`, read each user's New York time, steps, nag counts, phone heartbeat age and verdict. | Verified numbers only, the reminder window, the 2-hour damping, the daily cap and the phone stand-down (`gates.rs`). The cron job is deleted while WhatsApp is off (since 2026-11-15). |
| `/internal/failover-sync` | Start the cloud Clozemaster sync for users with autonomous sync on. | Users whose stats are under 100 minutes old are skipped (`gates::failover_decision`). Costs Akamai invocations and Clozemaster requests, not money. |

So a leaked key costs privacy (dry-run activity data) and a little nuisance. It does not open a route to cloud spend. Rotate it when it may have reached anyone else: a commit, a log, a screenshot, a shared terminal. A local AI session reading `.env` is not by itself a reason.

#### Rotating `INTERNAL_API_KEY`

The cron jobs carry the key in their query string, so the old key stops working for them the moment the new deploy is live. Do steps 2 and 3 back to back. Refusals in between are counted in `internal_refusals` as `bad_key`, and the narrator shows them; that's expected during a rotation.

1. **New key in `.env`.** `openssl rand -hex 32`, then replace the `INTERNAL_API_KEY=` value in the project root `.env`. Don't paste it anywhere else.
2. **Deploy:** `./mecris-go-spin/sync-service/deploy-akamai.sh` (it passes `internal_api_key` to Spin). Wait until `spin aka app status` shows Serving.
3. **Recreate the crons.** `spin aka cron list` prints the old key, so never paste its output. Then `spin aka cron delete failover-sync` (and `trigger-reminders`, if it exists), then `./scripts/setup_spin_cron.sh`. While WhatsApp is off, delete `trigger-reminders` again afterwards (`spin aka cron delete trigger-reminders`), because the script recreates both jobs.
4. **Verify:** `./scripts/verify_spin_deploy.sh` (a dry run by default). It reads the new key from `.env`, checks that no key and the burned `test-internal-key` are refused, and runs a cron-shaped `failover-sync`. At the next `:05` past an even hour, the pulse should show a fresh AKAMAI FUNCTIONS `sync ...` status.
5. **Nothing else changes.** The Android app uses the user's bearer token, not this key. CI generates its own key per run. The local MCP server doesn't call these routes.

`GET /internal/trigger-reminders?dry_run=1&key=...` reports, per user (by `familiar_id`), the New York time, steps, minutes since the last nag, nags today, the phone heartbeat age, the verdict and reason, and the template variables. It sends nothing and writes nothing.

### Status and nag routes (v0.3.0)
All three need a signed-in user's bearer token and act only for that user. None takes the internal cron key.

**`GET /claude-plan`** returns the caller's Claude plan state (#344), worked out from their newest `claude_plan_usage_readings` row. The plaintext `notes` column is never read. `age_minutes` is whole minutes against the database clock, never below 0 (a status line reading's `observed_at` comes from the writer's clock, which can run a moment ahead). The body is one object: `state`, `reason`, `stale`, `summary_line`, `plan`, `verified`, `source`, `observed_at`, `age_minutes`, and `windows[]` (`kind`, `pct_used`, `resets_at`, `fresh`). `source` is `manual` or `claude_code_cli` (the Claude Code status line, #383, usually minutes old and never with a `weekly_fable` window); `pct_used` is a float and may be fractional; `resets_at` is passed through as stored, with whatever UTC offset it was written in. The state comes from the fullest window that has not reset yet: `exhausted` at 100% used or more, `constrained` over 80%, otherwise `available`. A reading over 24 hours old, or one whose weekly reset has already passed, reads as `unknown`. With no reading (or no table) the answer is still 200, with the `unknown` "no reading recorded" object. The truth table is `contracts/claude_plan_cases.json`, shared with the Python and Kotlin arms.

**`GET /aggregate-status`** now always carries `pace[]`, one entry per language goal (`goal`, `remaining`, `per_hour`, `clear_by`, `due_today`): the reviews left today and the hourly pace that clears them by 22:00 America/New_York. In the last hour before 22:00, and after it, `per_hour` equals `remaining`. Without `?full=true`, `claude_plan` is `null`. A past `vacation_mode_until` no longer counts as a vacation for `all_clear`. The phone's nag workers read pace from this light call (#349).

**`GET /aggregate-status?full=true`** adds:
- `claude_plan`: the same object as `GET /claude-plan`, or `null` when the caller has no reading;
- `modalities[]` (also mirrored as `system_pulse.modalities`): the system pulse (#346), one line per `scheduler_election` role (`role`, `status`, `last_seen`, `minutes_since`, `last_status`). The registry is `contracts/pulse_roles.json`. `leader` is healthy under 2 minutes and degraded under 5. `android_client` is healthy under 90 and degraded under 240. `akamai_functions` is healthy under 135 and degraded under 250. Anything older is offline. `active_ghost` always shows as `paused`. `fermyon_cloud` and `unknown_cloud` are retired and never shown. Any other role shows as `unknown`, and only while it is under 24 hours old. Each role is shown once; the newest heartbeat wins. Only cron runs stamp `akamai_functions`, and `GET /health` writes no pulse row, so an offline AKAMAI FUNCTIONS line means the cron stopped. A cron run with an unset or unrecognised `cloud_provider` also reports as `akamai_functions`; the `unknown` role is no longer written.

The full shape is pinned by `contracts/spin_aggregate_status_full.json`.

**`POST /internal/log-message`** records that the phone showed a local nag (#213). Body: `{"type": "walk_reminder" | "arabic_pressure" | "greek_reminder", "sent_at": "<RFC 3339, optional>"}`. It writes one `message_log` row: channel `android_native`, status `shown`, no content, and `date` set to the New York date of `sent_at`. A `sent_at` that is missing, unparseable, in the future or over 24 hours old is replaced by now. Channel, status and content are never taken from the body. Answers: 201 `{status, message}`, 400 for a bad body or a type that is not a phone nag, 401 without a bearer, 404 when the user does not exist. These rows count toward the 4-hour damping below, but never toward the WhatsApp daily cap.

### See what happens (#363, phase 1)
The shapes are `contracts/message_events.json`. Run `scripts/migrate_v10_message_events.py` (additive, idempotent) before deploying: it adds `message_log.client_ref`, `message_sid`, `delivery_status`, `delivery_error` and `status_updated_at`, the `message_events` table (one row per message, event and time), and `users.notifications_enabled` / `notifications_checked_at`. None of them holds message text, phone numbers or names.

- **`POST /internal/log-message`** also takes an optional `client_ref`: 1-64 characters from `[A-Za-z0-9-]` (the phone sends a random UUID), else 400. A repeat with the same user and `client_ref` writes nothing and answers 200 `Already logged`; a new nag answers 201. Without `client_ref` nothing changes.
- **`POST /internal/log-message-event`** (bearer): `{"client_ref", "event", "at"}`, where `event` is `tapped`, `dismissed`, `action_later` or `action_start`. The nag is found by the bearer's user and `client_ref` on channel `android_native`; the body never names a user. `at` is kept to the millisecond, so a retried upload is recorded once; missing, unparseable, future or over 24 hours old means now. Answers 201 inserted, 200 already recorded, 404 `Unknown nag`, 400 bad body, 401 without a bearer.
- **`POST /heartbeat`** stores `notifications_enabled` (notifications on and the nag channel not silenced) with `notifications_checked_at = now()` when the body has it as a boolean. The response is unchanged.
- **`POST /internal/twilio-status`** is Twilio's StatusCallback. Its `X-Twilio-Signature` is checked exactly like the webhook's, against `twilio_status_callback_url` (or the URL Spin saw), and fails closed; a bad signature answers 403 and is counted in `internal_refusals` as endpoint `twilio-status`, reason `bad_signature`. A signed callback finds the `message_log` row by `MessageSid`, moves `delivery_status` forward only (`queued` < `sent` < `delivered` < `read`; `undelivered` and `failed` are terminal), stores a numeric `ErrorCode` in `delivery_error`, and records the status once per message in `message_events`, even when it arrives late. An unknown SID or an untracked status (`accepted`, `sending`, ...) answers 200 and changes nothing.
- Every Spin WhatsApp send (walk reminder, verification code) stores Twilio's `sid` in `message_log.message_sid` with the initial `delivery_status`, and adds `StatusCallback` only when `twilio_status_callback_url` is set.

### Walk reminder gates (cloud WhatsApp is the fallback)
All local times are America/New_York (hard-coded; `users.timezone` is not read). A cloud walk reminder goes out only when every gate passes (`src/gates.rs`, truth table `contracts/nag_damping_cases.json`):
- `users.phone_verified` is true, and vacation is off (`notification_prefs.vacation_mode`, or `users.vacation_mode_until` in the future);
- today is in `enabled_days` (empty means every day) and `message_types` (if set) includes `walk_reminder`;
- the hour is within `time_window_start`..`time_window_end`, both inclusive (14/17 is 14:00 to 17:59);
- no 2000+ step walk today;
- the phone's `android_client` heartbeat is at least `reminder_standdown_minutes` old (Spin variable, default `240`; `0` turns the stand-down off);
- no nag on any channel in the last 240 minutes (WhatsApp sent/failed, or an `android_native` nag shown);
- fewer than `max_messages_per_day` (default 3) WhatsApp nags today, counted by `sent_at` in New York.

Twilio secrets are loaded only when a send is due.

### Production Delivery Mandate (No Console Mode)
Akamai Functions must **never** be deployed in `console` mode. Cloud cron executions dispatch outbound WhatsApp alerts via the approved Meta Utility template pool and record every send attempt (sent or failed, no content) in `message_log`. Every cron run records its outcome per user in `scheduler_election.last_status` (role `akamai_functions`, intent `cron`, heartbeat now, PII-free `last_error`), e.g. `reminders 20:00Z: stood down (android active 35m); sync 20:05Z: fresh 40m`. Stand-downs and skips never go to `message_log`, whose cooldown readers ignore status. Refused callers of the cron endpoints and the webhook are counted in `internal_refusals` (one row per New York day, endpoint and reason: `no_key`, `bad_key`, `burned_key`, `probe`, `bad_signature`; `probe` is `scripts/verify_spin_deploy.sh`'s own wrong key, marked with the non-secret `verify-probe-` prefix, and like `burned_key` it never raises the narrator's bad_key alert); `scripts/migrate_v9_cloud_observability.py` creates the table.

**Private network dependency:** The Pocket ID JWKS is fetched from `https://metnoom.urmanac.com/.well-known/jwks.json` which is only accessible on the Tailscale/home LAN. This is why deployment runs locally, not in GitHub Actions.

---

## Verification After Deploy

```bash
# Get a valid token (via mecris CLI login)
TOKEN=$(cat ~/.mecris/credentials.json | jq -r .access_token)

# Test all authenticated routes
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/health
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/languages
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/aggregate-status
curl -H "Authorization: Bearer $TOKEN" "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/aggregate-status?full=true"
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/claude-plan
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/budget
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/profile

# Internal endpoints, refusals and cron outcomes: sends no WhatsApp by default
# (dry run of trigger-reminders, a cron-shaped failover-sync, read-only Neon checks)
./scripts/verify_spin_deploy.sh

# Component liveness (no auth required)
curl -X POST -H "Content-Type: application/json" \
  -d '{"debt":1138,"tomorrow_liability":37,"daily_completions":0,"multiplier_x10":10,"unit":"cards"}' \
  https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/internal/review-pump-status
```

All authenticated routes must return **200** (not 401). A 401 means `oidc_jwks_json` was missing from the deploy.

---

## What Was Fixed (2026-07-31)

### 1. Buggy `calculate_targets` Formula
**File:** `mecris-go-spin/sync-service/src/lib.rs`

**Wrong:** `target = (cur + tom) / rate`
**Correct:** `target = tomorrow_liability + current_debt / clearance_days`

Now matches the review-pump component and Python `review_pump_core.py`.

### 2. Missing `oidc_jwks_json` Variable
**Root cause of 64-day silent auth failure** (see `blog/2026-07-30-the-missing-variable.md`)

The `extract_user_id()` function requires this variable to verify Pocket ID RS256 tokens. Without it, ALL authenticated routes return 401 even with valid tokens.

---

## Android App Configuration

`mecris-go-project/app/src/main/java/com/mecris/go/BackendManager.kt`:
```kotlin
"Akamai Cloud" to "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/"
```

---

## Rollback / Redeploy

Just run `./deploy-akamai.sh` again. It's idempotent and atomic.

---

## Files Modified in This Fix

1. `mecris-go-spin/sync-service/src/lib.rs` — fixed `calculate_targets()` + added `clearance_days()`
2. `mecris-go-spin/sync-service/deploy-akamai.sh` — new foolproof deployment script
3. `mecris-go-spin/DEPLOYMENT.md` — this document