# Changelog

All notable changes to Mecris are documented here.

## [0.1.0] — 2026-09-30 — "The Odometer"

The release that made the money systems real: the Helix billing balance became an
odometer — charted, change-gated, edge-primary.

### Added

- **Helix balance odometer (task 588)**: Android app → `POST /helix-balance/request`
  → Rust Spin edge (Akamai) syncs **inline**: wallet read (per-user encrypted
  token) → `helix_balance_log` → change gate (unchanged = silence, R3) →
  straight-copy datapoint to Beeminder goal `helix-ml`. The laptop MCP leader job
  is the fallback; edge/leader races dedupe at Beeminder (422 = success).
- `scripts/helix_balance_scraper.py` (Python twin + CLI) and
  `scripts/migrate_helix_balance_log.py` (Neon tables `helix_balance_log` /
  `helix_balance_requests`; `users.helix_api_token_encrypted`).
- MCP tools `sync_helix_balance` / `get_helix_balance_status`; narrator and
  `get_budget_governor_status` carry `live_balance` with explicit provenance
  (`live` / `unavailable`; per-bucket `limit_source: env|default`) — defaults can
  never masquerade as truth (R9).
- Failure instrumentation: `helix_balance_log.last_error` (typed reason, persisted
  and echoed in the API response); `helix_balance_dark` SMS alert after ≥2
  consecutive fetch failures — the ghost lesson.
- Android hook: `requestHelixBalanceSync` on the 15-min `WalkHeuristicsWorker`
  heartbeat + dashboard open. The app is response-agnostic (additive DTO fields;
  no APK change for backend evolution).
- Edge config: `helix_api_base_url` / `helix_billing_org_id` Spin vars;
  `https://app.helix.ml` in `allowed_outbound_hosts`.
- Agent skills: `mecris-edge-sync-e2e` (E2E runbook + witness scripts) and
  `witness-driven-debugging` (cross-boundary debug method).

### Fixed / hardened

- `make deploy-akamai` / `deploy-fermyon` now delegate to the canonical
  `deploy-*.sh` scripts: partial `--variable` lists silently reset omitted Spin
  vars to defaults (a live bug once wiped `twilio_auth_token_encrypted` and
  `internal_api_key` mid-session).
- Postgres `to_char` syntax for reading timestamps (strftime `%s` leaked through).
- Cloudflare-safe header set on the edge wallet fetch (lever UA + Accept +
  `org_id` param; the bare client was 403/1010'd).

### Notes

- **Accepted risk (S6)**: the Helix billing API token is write-capable — no
  read-only scope exists upstream today. Upstream asked; see
  `docs/HELIX_API_FEEDBACK.md`.
- Built by an informal agent-to-agent team: Qwen (Helix sandbox) on the code,
  Gemini 3.1 Pro / 3.8 Flash (Antigravity CLI) on the phone, witnesses, and docs,
  with the operator as the human deploy/consent gate. The shared branch, the Neon
  witness tables, and the skill pair were the transport. See
  `docs/HELIX_BALANCE_SYNC.md`.
