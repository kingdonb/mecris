# The Missing Variable: How One JWKS Unblocked 64 Days of Silent Failure

**Date:** 2026-07-30  
**Tags:** [mecris, akamai, spin, oidc, android, debugging]

---

## The Symptom

The Android app could sync walks, language stats, budget, and Beeminder goals — but only when I ran the local Python MCP server on my laptop. The cloud API on Akamai (`mecris-sync-v2`, deployed since May 27) returned `401 Unauthorized` on every authenticated route, even with a valid Pocket ID access token.

```
/profile        → 401
/aggregate-status → 401
/languages      → 401
/budget         → 401
/walks POST     → 401
/internal/cloud-sync → 401
```

But the public routes worked:
```
/health                    → 200
/internal/review-pump-status → 200
/internal/failover-sync    → 200 (with internal API key)
```

The deployment was alive. The database was reachable. The cron triggers fired every 2 hours across 20+ edge regions. **Only OIDC verification was broken.**

---

## The Root Cause

The Spin component `sync-service` uses `jwt_simple` to verify RS256 tokens from Pocket ID. The verification logic in `extract_user_id()` (in `mecris-go-spin/sync-service/src/lib.rs`) requires the JWKS to be provided via the `oidc_jwks_json` Spin variable:

```rust
let manual = variables::get("oidc_jwks_json").await.ok()?;
let jwks: Jwks = serde_json::from_str(&manual).ok()?;
```

This variable was declared in `spin.toml` but **never set on the Akamai deployment**. Without it, `extract_user_id` returns `None` → every protected route returns 401.

The variable existed in config. The code expected it. The deployment just... didn't have it.

---

## The Fix

One redeploy with the missing variable (plus all the other required secrets):

```bash
cd mecris-go-spin/sync-service
spin aka deploy --build --no-confirm --skip-readiness-check \
  --variable db_url="postgresql://..." \
  --variable neon_db_url="postgresql://..." \
  --variable master_encryption_key="****" \
  --variable internal_api_key="test-internal-key" \
  --variable clozemaster_email="..." \
  --variable clozemaster_password="****" \
  --variable twilio_account_sid="****" \
  --variable twilio_auth_token_encrypted="****" \
  --variable twilio_from_number="+15744757115" \
  --variable openweather_api_key="****" \
  --variable oidc_jwks_json='{"keys":[{"alg":"RS256","e":"AQAB","kid":"tmUpnrhx6gk","kty":"RSA","n":"vqLb33vkC8oZ7NDdlcBfBztPOAue3ZWrMDNhk9fBU2xrX6WTiAofqGDe_JJDCywJfEyDY-ecfQEXc5pph4v9R5xRiGhel4hLfcdcUTV7FH6MehaufcTREh_khCuAhyMOvUNlhw63mTY0yDpmaHubkh8vyhJUvmzBxr1ZR2snnrbas9q_ASvhKBeinFiAwXYH7Jf8I6C7E5LjP4BO4_ft4P2KBdspKSSREgln_i-ntZCt0UgLgDcS5coNGrz8hw-3NLUKAgHG_5GFXKSuibTV86Esk6MSYSgtKdHLM4O59Hgyz4CPFI8s47jtsLbbpuo8nq-WHU1PtQoTE1IayAD0tQ","use":"sig"}]}' \
  --variable cloud_provider="akamai"
```

Deployed as **v64** (2026-07-30 19:16:38 UTC).

---

## Verification

Every authenticated route now returns 200:

| Route | Auth | Status |
|-------|------|--------|
| `GET /health` | Bearer | ✅ 200 |
| `GET /profile` | Bearer | ✅ 200 |
| `GET /aggregate-status` | Bearer | ✅ 200 |
| `GET /budget` | Bearer | ✅ 200 |
| `GET /languages` | Bearer | ✅ 200 |
| `POST /walks` | Bearer | ✅ 201 |
| `POST /internal/cloud-sync` | Bearer | ✅ 200 |
| `POST /internal/failover-sync` | x-internal-api-key | ✅ 200 |

**Android sync proof:** A test walk (2500 steps) posted → `/aggregate-status` shows `"walk":true` → Beeminder "bike" goal received datapoint `Value: 1.0, Comment: "Synced via Spin (Cumulative)"`.

**First successful cloud walk sync since 2026-05-27.** (64 days.)

---

## What This Reveals

### 1. No Observability on Auth Failures
The `spin aka logs` show request routing but not app-level 401/500 causes. The 5% envelope from the Budget Governor (39-min rolling window) is designed to catch this, but the auth path bypassed it — `extract_user_id` failing silently doesn't trigger a spend event.

**Fix needed:** Log `extract_user_id` failures to Neon `events` table (per Observability Mandate). Expose auth success/failure metric.

### 2. The Python MCP Server Was a Crutch
Its latency and availability issues masked the fact that the *canonical* Spin API was one variable away from working. The Python server should be dev/fallback only.

### 3. Fermyon Cloud Channel Is Dead
`mecris-sync-v2-r0r86pso.fermyon.app` returns platform 404. Akamai (`fwf.app`) is the only live edge deployment.

### 4. Configuration Drift Is Silent
`spin.toml` declares 16 variables. The deployment had ~3 set. No validation, no drift detection, no alerting.

---

## The Budget Governor Connection

While debugging, I traced through the Budget Governor — the fiscal intelligence layer that governs LLM spend across four buckets:

| Bucket | Type | Limit | Philosophy |
|--------|------|-------|------------|
| `helix` | SPEND | $100 | Use-it-or-lose-it SaaS credits |
| `gemini` | SPEND | $50 | Free tier, burn it down |
| `anthropic_api` | GUARD | $20.89 | Real money, ration carefully |
| `groq` | GUARD | $10 | Real money, ration carefully |

**Core rule (5%/5% envelope):** In any rolling 39-minute window, no more than 5% of a bucket's period quota may be spent. Hard stop at 100% of limit.

**Helix Inversion:** SPEND buckets are preferred; GUARD buckets are fallbacks. The governor recommends the bucket with the most remaining credits.

This logic exists in three places:
1. `services/budget_governor.py` — Python class (deprecated, kept for local MCP)
2. `poc/wasm/budget-governor-py/app.py` — WASM component (Spin KV + Variables, the cloud truth)
3. `tests/test_budget_governor.py` — TDG red-phase tests

The WASM component is the single source of truth for cloud. It persists spend log to Spin KV, reads limits from Spin Variables, and exposes HTTP actions: `status`, `check`, `record`, `recommend`, `gate`.

---

## Next Steps

1. **Add auth observability** to `sync-service`: log `extract_user_id` failures, expose `/internal/auth-health`
2. **Update `test_cloud_beta4_validation.py`** — it asserts `/health` returns 500; now returns 200 with auth
3. **Android app:** Point default backend to Akamai; verify failover when local is down
4. **Configuration drift detection:** Validate all `spin.toml` variables are set on deploy
5. **Decommission or re-deploy** Fermyon Cloud channel if redundancy is needed

---

## The Lesson

> **A deployment is not live until every variable its code expects is set.**

The code was correct. The infrastructure was correct. The database was correct. The token was correct. One missing JSON blob in a Spin variable turned a production API into a 401 generator for 64 days.

Sometimes the bug isn't in the code. It's in the config that never made it to the edge.