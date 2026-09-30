# Helix Billing API — field report from a production server-to-server client

Audience: Helix platform (Luke). From: the Mecris balance odometer (task 588), which charts
your `GET /api/v1/wallet` onto a Beeminder goal via an Akamai Functions edge. First
server-to-server consumer of the billing API we know of, running 24/7 from three client
classes: a laptop Python CLI/leader, a phone-triggered Rust/WASM edge, and (fallback) a
scheduler. Everything below is observed, not inferred — dates and evidence attached.

## What we consume

- `GET https://app.helix.ml/api/v1/wallet?org_id=mecris`, `Authorization: Bearer <hl- key>`
- Fields: `balance`, `subscription_current_period_end` (+ `org_id`, `subscription_status`).
- Cadence: one read per app-open + hourly ceiling; sub-cent precision preserved
  (`balance` arrives like `497.357482416`; we store 4 dp, chart 2 dp). Please keep the
  wallet response schema stable — this trio is our contract.

## Finding 1 — no read-only key scope forces a write-capable secret into a chart pipeline

Our pipeline needs *read*. Helix (as of 2026-09-30) has no read-only-scoped key, so we ship
a key that can do more. We hardened what we control — per-user AES-256-GCM encryption at
rest, transient decrypt in-request, never logged — but a leaked master key now implies
spend-capable money credentials. **Ask: scoped keys (e.g. `billing:read`).** Related
platform note we've already steered around: `GET /api/v1/users/<id>` echoes the caller's
own token in the response body — hostile-echo hazard for exactly this class of client.

## Finding 2 — Cloudflare in front of the API defeats honest server-to-server clients

- 2026-09-19 (M1 door-trace): headless clients without a curated header set get
  **403/1010** at the edge; we pinned a "Cloudflare-safe" set (custom `User-Agent`,
  `Accept: application/json`) to get through.
- 2026-09-30 probe: a datacenter-IP sandbox sending the lever UA reaches **origin** (401
  from Helix for a fake token) — the rules are not a blanket datacenter ban.
- 2026-09-30 production: the same request from **Akamai Functions egress fails**
  (`fetch_status='failed'`; root cause being pinned to the byte by our `last_error`
  witness — status-code snippet included, will follow up).
- **RESOLVED (2026-09-30, same evening):** the Akamai failure was **not** Cloudflare —
  our `last_error` witness surfaced `send: ErrorCode::HttpRequestDenied`, and the gate
  was our own runtime: the Spin component's `allowed_outbound_hosts` in `spin.toml`
  didn't list `app.helix.ml`, so the packets never left the edge. One manifest line
  (c7b90f7) later, wallet fetches from Akamai Functions succeed. **Cloudflare passed
  both the datacenter sandbox probe and the Akamai egress all along** — our
  browser-shaped-UA client was unnecessary paranoia on those paths. The Ask below
  stands (a documented server-to-server posture so integrators don't have to guess),
  but the evidence tilts friendly: CF honors honest `Bearer hl-…` traffic from
  serverless platforms today.

**Ask:** a documented server-to-server posture — CF rules that honor requests bearing a
valid `Authorization: Bearer hl-…`, and/or an allowlist process for known serverless
platforms. A client that presents a real API key shouldn't need a browser-shaped UA.

## Finding 3 — minor precision/display note

The billing page floors to 2 dp (`497.35`) while the API carries sub-cent truth
(`497.3575`); our odometer charts the API's 2-dp *round* (`497.36`). All three "agree" and
all three differ — worth one sentence in docs so integrators trust the API number, not the
page number, for metering.

## Contact

Mecris repo: `docs/HOW_MECRIS_WORKS.md` §7–§8 (odometer design), `docs/HELIX_BALANCE_SYNC.md`
(operational protocol), S5/S6 in the article's security-findings table. The `last_error`
column in `helix_balance_log` is the running evidence trail for Finding 2.
