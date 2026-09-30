# Helix Balance Sync — E2E Protocol (task 588, Type 3)

The chain, in one line: **Android app → POST `/helix-balance/request` → the Rust
edge syncs inline (wallet read → `helix_balance_log` → change gate → straight-copy
datapoint to Beeminder `helix-ml`) → response shows the newest reading. The laptop
leader is the fallback.**

Why edge-primary: Android + API must be able to do anything the MCP does for
budget data and Beeminder routing; the MCP job (C4) degrades to fallback — users
without a provisioned token, edge/wallet outages, and the hourly R1 pulse while
the laptop is open. Both actors share the Neon log + `requestid` scheme, so a
race dedupes at Beeminder (422 = already in).

## One-time setup (operator)

1. **Token (C6)** — create a **read-only** Helix API key at app.helix.ml →
   Settings → API keys. Put it in the laptop's Mecris `.env`:
   `HELIX_BILLING_API_TOKEN=hl-…` (same 1Password → `.env` pattern as
   `master_encryption_key`; never pastes into chat, logs, or git).
   The token never becomes a Spin variable: the leader's first sync
   (`provision_helix_token`) encrypts it into `users.helix_api_token_encrypted`
   (AES-256-GCM, the edge decrypts per-user like the Beeminder token).
2. **Migrate Neon (C2):** `python scripts/migrate_helix_balance_log.py`
   (uses `NEON_DB_URL` from `.env`; idempotent — includes the `users` ALTER).
3. **Deploy the edge:** `make deploy-akamai` (delegates to
   `deploy-akamai.sh` — the canonical deploy: sources `.env`, validates,
   encrypts Twilio, passes the FULL variable set; a partial `--variable` list
   silently resets omitted Spin vars to `spin.toml` defaults, which is how
   `twilio_auth_token_encrypted`/`internal_api_key` once got wiped). The
   `helix_api_base_url` variable defaults to `https://app.helix.ml`, so
   omitting it on deploy is safe.
4. **Build + install the app:** latest `feature/000588-chart-the-helix-billing`
   (the hook is in `WalkHeuristicsWorker` + dashboard refresh; Retrofit method
   `requestHelixBalanceSync`).
5. Restart Mecris on the laptop (MCP server = the scheduler leader). The first
   leader sync (CLI run, `sync_helix_balance` tool, scheduler tick, or scalar
   probe) provisions `users.helix_api_token_encrypted`. Until then, app POSTs
   are queued and the leader handles them at the next tick.

## Daily behavior (no action needed)

- App heartbeat (15-min WorkManager) piggybacks a balance request; opening the
  dashboard requests one immediately. The **edge syncs inline** (token
  provisioned): the POST response carries `pushed`/`synced` + newest reading.
- Leader fallback job `auto_helix_balance_*`: runs when a request is pending
  (edge queued it), else keeps the hourly cadence. Unchanged balance =
  **silence** (R3); moved balance = one new datapoint (`requestid` per reading;
  422 dedupe = success — races with the edge dedupe, not double).
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

1. Open the Mecris app dashboard → logcat: `Helix balance sync requested`;
   response `pushed: true, synced: true` (token provisioned) — no laptop needed.
2. Beeminder `helix-ml`: newest datapoint = today's wallet balance, lower than
   yesterday's; comment `Helix balance $… (source=api)`.
3. Re-open the dashboard a minute later: second request → edge sees the value
   unchanged → **silence** (no second datapoint). That no-op is half the test.
4. Laptop-off test (the point of this rev): spend in a Helix session, open the
   app, number drops **with the laptop shut** — edge-primary proven.
5. Leader (laptop on, ≤15 min): no duplicate datapoint on the next tick.
