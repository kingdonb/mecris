# Changelog

All notable changes to Mecris are documented here.

## [0.2.0] — 2026-11-14 — The cloud arm works

The Akamai cron jobs that drive cloud reminders and the nightly failover sync were
being refused with 401, and the reminder they trigger was sending over a disabled
channel. This release fixes the cloud path end to end and closes two security holes
found on the way. It also starts tracking the Claude subscription plan.

### Security

- **Twilio webhook verifies `X-Twilio-Signature`** (#365). The handler decrypted the auth token and never used it, so anyone who knew a user's phone number could log a walk for them. Requests without a valid signature now get 403. The yes check reads only the message text.
- **Internal endpoints fail closed** (#366). The key `test-internal-key` was committed in the deploy scripts of this public repository, and an unset key authorized everyone. The key now comes from `INTERNAL_API_KEY` in `.env`; an unset key or the published key authorizes nobody.
- **No PII in logs** (#364). Phone numbers and Twilio error text are no longer logged by the Python server, the Spin service or the Android app. Every Twilio attempt is still recorded in `message_log`, with only a status and numeric code.

### Fixed

- **Cron can authenticate** (#366). Akamai cron can only send a path and query, never a header, so the key is also accepted as a `key` query parameter. The Android app sends its bearer token when it triggers reminders.
- **Spin sends WhatsApp templates, not SMS** (#368). SMS is disabled for the account. Walk reminders and verification codes now use the `mecris_status_v2` template, with no SMS fallback.
- **`message_log` inserts from Spin** (#364) had been failing silently since July (a column that does not exist), which also broke the reminder cooldown.
- **Expired budget period is "stale", not "BUDGET CRITICAL"** (#345, part 1).

### Added

- **Claude plan usage** (#344, part 1): `record_claude_plan_usage` and `get_claude_plan_status` tools, a `claude_plan` section in the narrator context, and a line in the Pi status.
- **Beeminder graph of Claude usage** (#371): each recorded reading pushes a running total to the goal named by `CLAUDE_BEEMINDER_GOAL`.
- **`GET /version`** on the Spin API: public, returns the deployed version and cloud provider.
- **`scripts/verify_spin_deploy.sh`** (#183): a post-deploy check that waits for the new version and then tests as the cron does.
- **Blog** at https://kingdonb.github.io/mecris/, built from `blog/*.md` by `blog/build.py`.

### Changed

- Deploy scripts require `INTERNAL_API_KEY` and `TWILIO_WHATSAPP_FROM`, and use the project virtualenv for token encryption.
- `scripts/setup_spin_cron.sh` creates the three cron jobs that exist, with the key in the query string.
- `scripts/bump_version.py` also bumps the sync service's `Cargo.toml` and `Cargo.lock`.

### Removed

- Dead Android `BeeminderApi` (#66). The app talks to Beeminder only through the Spin API.

### Upgrade notes

Tagging does not deploy the Spin API. Follow steps 8 and 9 of `docs/RELEASE_PROCESS.md`. If a genuine WhatsApp reply is rejected after deploying, set `TWILIO_WEBHOOK_URL` to the URL configured in the Twilio console and redeploy.

## [0.1.4] — 2026-10-04 — Battery diet: 8 hr → ~2 hr background

The Android app showed 8 hr 11 min of background battery time against 26 min of
screen time. Root cause: a 15-minute WorkManager heartbeat (~96 runs/day) plus,
after the 0.1.2 due-today change, near-continuous nag-worker runs that paid for
weather fetches, Health Connect reads, and on-device Gemini Nano inference
*before* their cooldown check — which then usually suppressed the nag. This
release cuts the cadence and the per-run cost; nag firing behavior, sync
semantics, and the deliberate battery-optimization exemption are unchanged.

### Fixed

- **Background battery drain** (target ≤ ~2.5 hr/day, from 8 hr 11 min): background network calls drop from ~500–700/day to under ~120/day — heartbeat ~24 runs/day + ≤ ~14 helix-balance requests + ≤ ~28 aggregate polls.
- **Cheap-first nag worker**: target selection, hour gates, and cooldown checks (SharedPreferences only) now run before any weather fetch / Health Connect read / Gemini Nano inference; the LLM narrative is generated only when a nag will actually fire. Hierarchy, cooldowns (4 h default, 1.5 h Moussaka exception), weather fallthrough, and all messages unchanged.
- **Aggregate-only debt detection**: dropped `GET /languages` + client-side pump math from the background path — the edge already folds pump + Beeminder due-today into `aggregate-status` components (`goal_met = pump_met AND due == 0`).

### Changed

- **Hourly heartbeat**: periodic `WalkHeuristicsWorker` 15 → 60 minutes, with `ExistingPeriodicWorkPolicy.UPDATE` so the new interval replaces the already-enqueued 15-min schedule on upgrade (no cold start needed), plus a `NetworkType.CONNECTED` constraint.
- **Quiet-hours gate**: the debt/nag evaluation phase runs only 08:00–22:00 America/New_York; heartbeat and walk upload remain 24 h (leader gating + night walks).
- **Helix-balance throttle**: the `POST /helix-balance/request` doorbell fires at most once per 60 minutes during waking hours (`last_helix_request` pref). The edge runs its upstream Helix fetch inline in this request, so this also cuts phone radio time.

### Added

- **Run instrumentation**: one `WORKER_METRIC` log line per worker run (duration_ms + executed phases) — the falsifiable witness for the before/after battery lap.

## [0.1.3] — 2026-10-01 — Beeminder safebump & epoch road fix

Fixed Beeminder due-today calculation for sparse/epoch fullroad data and honored `safebump`.

### Fixed

- **Beeminder `safebump` prioritization**: Beeminder's goal JSON provides `safebump`, which represents the exact red line value at deadline time. When `safebuf == 0`, `safebump` is the authoritative red line threshold for today.
- **Unix epoch timestamp parsing in road math**: In Beeminder API, `fullroad` row timestamps are Unix epoch seconds (`t > 100_000_000`), not `YYYYMMDD` integers. The parser now converts epoch seconds to `America/New_York` calendar dates in both Python (`services/beeminder_road.py`) and Rust (`sync-service/src/lib.rs`).
- **Road interpolation between vertices**: Sparse `fullroad` rows without intermediate calendar days are interpolated between bounding vertices using the segment's daily rate.
- **Buffer check (`safebuf >= 1`)**: When `safebuf >= 1`, the goal cannot derail today, guaranteeing `beeminder_due_today == 0`.
- **Constructive interference UI alignment**: Recomputed `flow_fill_ratio` and `is_play_mode` against effective remaining targets; when Beeminder demands cards (e.g. 160 cards due), PLAY MODE turns off cleanly and remaining cards reflect the true requirement.

## [0.1.2] — 2026-10-01 — Constructive interference

The review pump and Beeminder stopped lying to each other. On 2026-10-01 a
massive Clozemaster card dump landed in the review stack (257 cards) while the
Beeminder `reviewstack` goal sat at safebuf 0 — "limit 86 today, −171 today" —
but the app showed REMAINING TODAY: 18. The interference rule existed
(`max(pump, Beeminder)`) but its Beeminder side computed `-safebuf` — a count
of safe **days**, 0 exactly on beemergency day — instead of a card deficit, so
it contributed nothing precisely when it mattered.

### Fixed

- **Beeminder due-today is now computed from the goal's own road**: the scraper
  already downloaded the full goal JSON and threw everything away except
  `safebuf`/`rate`; now it reads `yaw`, `curval`, and `fullroad`, finds the
  road limit at the end of today (America/New_York — hardcoded, per operator
  ruling), and stores `beeminder_road_today` + `beeminder_due_today` on
  `language_stats` (Neon migration included). Do-less goals owe
  `cur − road_today`; do-more the reverse; fractional demands ceil ( flooring
  would leave a do-less datapoint above the road); missing/malformed road or
  yaw fabricates nothing (due 0).
- **Interference happens at the REMAINING level**: `remaining =
  max(pump_remaining, beeminder_due)` and `quota = done + remaining`. Beeminder
  due is already net of cards done (curval falls with each sync), so taking
  the max at target level would double-count completions. The displayed quota
  stays stable as cards are completed.
- **Goal not met while Beeminder stands**: `goal_met = pump_met AND due == 0`
  in `GET /languages`, `aggregate-status` (arabic/greek components), and the
  Python velocity path — the pump goal is not "met" until the Beeminder
  derailing obligation is dispatched. Languages without a Beeminder slug keep
  pump-only semantics (their due is always 0).
- **Python parity (executable spec)**: the math lives in pure module
  `services/beeminder_road.py` (17 unit tests incl. the incident fixture
  257/86/yaw −1 → 171); Rust mirrors it (16 tests, `cargo test --lib`).
  WhatsApp reminder "cards needed" now shows the honest number.
- **Witness hooks**: a `safebuf >= 1` but `due > 0` canary logs loudly (road
  parse or yaw-sign suspect); an API-`delta` cross-check is logged per sync for
  sign-convention validation.

### Notes

- PLAY MODE badge turning off when Beeminder dominates is intended: playing
  doesn't remove cards from the stack; a derailing goal demands removal.
- Daystamps never subtract linearly (20261001 − 20260930 = 71): road
  extrapolation converts to real dates in both twins.
- `sync-service` crate gains an `rlib` crate-type so `cargo test --lib` can
  run the unit tests (full host `cargo test` still can't link the spin
  cdylib — pre-existing).
- Helix budget governor (0.1.0) untouched by construction; post-deploy
  `check_witnesses.py` must show fresh `ok` rows (guardrail).

## [0.1.1] — 2026-09-30 — The Odometer, steady-state fix

### Fixed

- **R3 change-gate oscillation (post-mortem):** the gate anchored `last_pushed`
  on the *newest* `ok` log row — and every silent lap logs a new `ok` row with
  `pushed_value` NULL, so the next lap saw no anchor and re-pushed an unchanged
  value (each with a fresh minute-resolution `requestid`, invisible to Beeminder's
  422 dedupe). Cadence: push → silence → push, every other heartbeat. The frozen
  overnight balance exposed it (15 duplicate datapoints); daytime spending masked
  it. Both twins fixed in lockstep (Python `_fetch_last_pushed`; Rust same SQL
  shape): the gate anchors on the newest **actual push** anywhere in history.
  Lap-three regression test added (fails on the old code). Charted values were
  never harmed — same-day odometer updates aggregate (`aggday: last`).
- Version bump only; no Android behavior change (VC 35 → 36 for install parity).

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
