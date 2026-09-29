# Helix Balance Sync — E2E Protocol (task 588, Type 3)

The chain, in one line: **Android app → POST `/helix-balance/request` (Rust edge) →
Neon `helix_balance_requests` → laptop leader polls (C4 job, 15 min) → wallet read
(C1a) → `helix_balance_log` row (C2) → change-gated straight-copy datapoint →
Beeminder `helix-ml`.** The sink never feeds anything back (R8).

## One-time setup (operator)

1. **Token (C6)** — create a **read-only** Helix API key at app.helix.ml →
   Settings → API keys. Put it in the laptop's Mecris `.env`:
   `HELIX_BILLING_API_TOKEN=hl-…` (same 1Password → `.env` pattern as
   `master_encryption_key`; never pastes into chat, logs, or git).
2. **Migrate Neon (C2):** `python scripts/migrate_helix_balance_log.py`
   (uses `NEON_DB_URL` from `.env`).
3. **Deploy the edge:** redeploy `sync-service` (the `make deploy` /
   `deploy-akamai.sh` flow) so `POST /helix-balance/request` exists in the cloud.
4. **Build + install the app:** latest `feature/000588-chart-the-helix-billing`
   (the hook is in `WalkHeuristicsWorker` + dashboard refresh; Retrofit method
   `requestHelixBalanceSync`).
5. Restart Mecris on the laptop (MCP server = the scheduler leader runs the job).

## Daily behavior (no action needed)

- App heartbeat (15-min WorkManager) piggybacks a balance request; opening the
  dashboard requests one immediately.
- Leader job `auto_helix_balance_*`: runs when a request is pending, else keeps
  an hourly cadence. Unchanged balance = **silence** (R3); moved balance = one
  new datapoint (`requestid` per reading; 422 dedupe = success).
- Fetch failures log `fetch_status='failed'` rows and push **nothing**; ≥2 in a
  row fires one SMS/day (`message_log` type `helix_balance_dark`) — the ghost
  lesson.
- Top-up day (the 17th): the straight copy lifts the plot over the road.
  Expected, benign, **nobody spends** because of it.
- Narrator + `get_budget_governor_status` now carry `live_balance`
  with explicit provenance (`live` / `unavailable`, per-bucket
  `limit_source: env|default`) — defaults can never masquerade as truth (R9).

## Verify by hand (M3/M4 gates)

```bash
python scripts/helix_balance_scraper.py --scalars   # read-only scalars
python scripts/helix_balance_scraper.py --dry-run   # show the push decision
python scripts/helix_balance_scraper.py             # the sync itself
```

MCP equivalents: `sync_helix_balance` (hand-drive tool), `get_helix_balance_status`.

## E2E acceptance (the number must go DOWN)

Precondition: you've spent Helix credits today (this session counts).

1. Open the Mecris app dashboard → logcat: `Helix balance sync requested`.
2. Laptop leader (≤15 min): scheduler log `Helix balance datapoint pushed`.
3. Beeminder `helix-ml`: newest datapoint = today's wallet balance, lower than
   yesterday's; comment `Helix balance $… (source=api+app_request)`.
4. Re-open the dashboard a minute later: second request → leader sees the value
   unchanged → **silence** (no second datapoint). That no-op is half the test.
