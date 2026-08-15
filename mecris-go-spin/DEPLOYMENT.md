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

### 2. Fermyon Cloud (Experimental / Inactive)
```bash
cd mecris-go-spin/sync-service
./deploy-fermyon.sh
```

Both deployment scripts:
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

### Production Delivery Mandate (No Console Mode)
Akamai Functions must **never** be deployed in `console` mode. Cloud cron executions must dispatch outbound WhatsApp alerts via the approved Meta Utility template pool and record delivery status or stand-down rationale directly to Neon Postgres (`message_log` table).

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
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/budget
curl -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/profile

# Test internal endpoints
curl -H "x-internal-api-key: test-internal-key" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/internal/failover-sync

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