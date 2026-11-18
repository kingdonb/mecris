# Changelog

All notable changes to Mecris are documented here.

## [Unreleased]

### Changed

- **The Claude Beeminder goal uses the odometer's own reset** (#390). Each reading is pushed as that week's percentage, as Claude reports it. At a weekly reset a `0` datapoint with `@TARE` in the comment goes first, timestamped at the reset, which is how Beeminder odometer goals start over. Before this, Mecris kept its own running total (each week's peak, added up) and pushed that. The tare is sent with every push of the week under one request id, so a tare that failed is retried, and a reading is held back if its tare cannot be sent. `BeeminderClient.add_datapoint` takes an optional `timestamp`.

- **Budget can follow the Helix monthly grant** (#393). New `source_type` `helix_grant`, which needs `scripts/migrate_v11_helix_grant_budget.py`. The period is the wallet's own (`subscription_current_period_start`..`end`), so it rolls over by itself and is never stale. "Used" is what the balance dropped since the period started, with inflows excluded. Spending past the grant raises nothing: this tracks, it does not ration. `HELIX_TARGET_BALANCE` and `HELIX_TARGET_DATE` set an optional target. The narrator, CLI pulse and Pi `/status` then show the daily pace that reaches it, counting grants still to land, and say so when the pace is above `HELIX_BURN_CAP`.
- **Helix daily burn cap is $6, up from $5** (owner's decision, 2026-11-17). Both spend-down targets on #393 need more than $5/day: about $5.39/day for $500 by 2026-12-31, and about $5.84/day for $0 by mid-2027. The default lives in one place, `HELIX_BURN_CAP_DEFAULT` in `scripts/helix_balance_scraper.py`; `HELIX_BURN_CAP` still overrides it.

### Fixed

- A record-tool test had a weekly reset date written in, and began failing once that date passed.

## [0.3.0] — 2026-11-14 — Reminders only when they should

0.2.0 let the Akamai cron reach the reminder endpoint. The checks behind that endpoint were broken, and on 2026-11-14 the cloud sent five WhatsApp walk reminders between 04:59 and 12:59 New York time. The `trigger-reminders` cron job was deleted at 19:40 UTC that day and stays off until this release is deployed. This release rebuilds the reminder gates, records every cron run and every refused cron or webhook request, moves periodic language sync to the cloud, fixes phone verification, and stops the phone from triggering cloud work. Claude plan usage now comes from the Claude Code status line instead of hand-entered readings. The Python server, the Spin API and the Android app are now tested against the same rules, kept in a new `contracts/` directory.

### Corrections to 0.2.0

- **The `message_log` insert fix did not restore the walk reminder cooldown.** The 0.2.0 entry said the broken insert "also broke the reminder cooldown", which implied the fix restored it. It did not. The cooldown read `sent_at::TEXT`, which Neon prints with an hour-only offset (`+00`) that neither of Spin's timestamp parsers accepts, so the last reminder always read as "never sent". Two of the sends on 2026-11-14 were 119.9 minutes apart, inside the 2-hour cooldown.
- **Verification sends were not logged.** The 0.2.0 entry said every Twilio attempt is recorded in `message_log`. In Spin that held for walk reminders only. Phone verification codes were sent without a row.
- **The cloud reminder gates were broken**, so five reminders went out at the wrong hours on 2026-11-14 (at 04:59, 07:00, 09:00, 10:59 and 12:59 EST; Twilio accepted all five):
  - quiet hours used `users.timezone`, which holds the column default `UTC` and is written by nothing, so the 09:00–20:59 window ran 04:00–15:59 in New York;
  - the 2-hour cooldown never applied (above);
  - the stand-down while the phone is active never fired. The heartbeat age arrives from Postgres as a numeric (`DbValue::Decimal`), and the code matched only a float. The 12:59 send went out 30 minutes after a phone heartbeat;
  - `notification_prefs` were ignored, so the 14:00–17:59 window and the 3-a-day cap had no effect.
- **Also broken in 0.2.0:**
  - `failover-sync` could never sync: its age is also a numeric, so it read as 0 minutes against a 1440-minute gate;
  - reminders went to a number that had never been verified;
  - the app's VERIFY flow could not finish, because Spin answered with bare JSON strings the app cannot parse;
  - `scripts/verify_spin_deploy.sh` made a real `trigger-reminders` call by default, which sends a WhatsApp reminder when run inside the window.
- **Don't install the 0.2.0 APK** (versionCode 40). Its reminder call carries a bearer token that the 0.2.0 API accepts, so it would add sends through the broken gates. Use versionCode 41. The v0.2.0 release notes now carry this warning.

### Spin API (cloud)

- **Reminder gates rebuilt** (#368, #349, #183). Spin decides in America/New_York time (the window, the weekday, "today" for steps, and the time shown in the message) and no longer reads `users.timezone`. It honors `notification_prefs`: the window (start and end hours both inclusive, so 14–17 means 14:00–17:59), `enabled_days`, `message_types` and `vacation_mode`. It also skips users whose `vacation_mode_until` is still in the future. Only users with `phone_verified` are eligible.
- **Damping, cap and stand-down that work.** No WhatsApp reminder within 4 hours of another nag on any channel, counting failed sends and nags shown on the phone. At most `max_messages_per_day` (default 3) WhatsApp sends per New York day, counted by `sent_at`; nags shown on the phone don't count toward the cap. No send while the phone's heartbeat is younger than the new `reminder_standdown_minutes` Spin variable (default 240; 0 turns the stand-down off). Every gate age is computed in SQL as whole minutes and every count as an integer; Spin no longer parses timestamp text.
- **`trigger-reminders` explains itself.** It returns `{sent, failed, stood_down, reasons}`. With `?dry_run=1` it reports each user's New York time, inputs, verdict and reason, and sends and writes nothing. Twilio secrets load only when a send is due, and one user's error no longer stops the loop.
- **Cron key only** for `/internal/trigger-reminders` and `/internal/failover-sync`. The signed-in bearer path added in 0.2.0 is removed, along with the unused `handle_cron` and the `spin-cron-sdk` dependency.
- **Every cron run leaves a record** (#183, #245). Each run updates the user's cloud row in `scheduler_election` (role `akamai_functions` unless the `cloud_provider` Spin variable says `fermyon`) with a heartbeat, a one-line `last_status` (for example `reminders 20:00Z: stood down (android active 35m)`) and a PII-free `last_error`.
- **Refusals are counted.** A new `internal_refusals` table keeps one row per New York day, endpoint and reason (`no_key`, `bad_key`, `burned_key`, `probe`, `bad_signature`). A key starting with `verify-probe-` is the deploy check's own wrong-key test: it is refused and counted as `probe`, never as `bad_key`, so it raises no alert.
- **`failover-sync` syncs** (#183). It scrapes Clozemaster when the latest `language_stats` reading is 100 minutes old or more, or missing. Otherwise it records `fresh N m`. It writes `last_autonomous_sync` after a successful scrape. The cloud now owns periodic Clozemaster-to-Beeminder sync.
- **Phone verification works** (#369, #358). Both verification endpoints return `{status, message}` objects the app can parse. A request stores the requested number on the caller's row, unverified, so the number that gets confirmed is the one that received the code. Saving a profile with an unchanged number keeps it verified. Requests are throttled (one a minute and five per New York day, then 429). Every verification send is logged as `phone_verification`, `sent` or `failed`, with no content.
- **Inbound messages leave a trace.** Every signature-verified inbound message writes a `received` row with no content. A walk acknowledgement needs YES as a whole word, so "yesterday" no longer logs a walk.
- **Spin's `message_log` rows carry the New York date.** Every row Spin writes sets `date` to the America/New_York date, as the Python reminder path does; 0.2.0 wrote the database's UTC date.
- **`GET /version` reports `"dry_run": true`**, so the verify script can tell a 0.3.0 service from an older one.
- **Claude plan and review pace** (#344, #349). `GET /aggregate-status?full=true` adds `claude_plan` (from the latest reading, null when there is none) and pulse modalities with `last_status`. `pace[]`, the reviews left today and the hourly pace needed to clear them by 22:00 New York time, is on the plain call too; in the last hour before 22:00 and after it, `per_hour` is the whole remainder. New `GET /claude-plan`, scoped to the bearer. Its `age_minutes` is whole minutes from the reading's `observed_at` to the database clock, rounded down and never below 0, so a status line reading stored from a clock slightly ahead of Neon reads 0 minutes old, not -1. Status line readings (source `claude_code_cli`, fractional `pct_used`, UTC `resets_at`, no `weekly_fable`) are read like manual ones.
- **`POST /internal/log-message`** (#213), which the app already called and got 404. It needs the bearer, accepts `walk_reminder`, `arabic_pressure` and `greek_reminder`, stores channel `android_native`, status `shown`, the New York date and no content, and answers 201.
- **Pulse follows `contracts/pulse_roles.json`** (#346). Retired roles (Fermyon, unknown cloud) are hidden, GHOST shows as paused, unknown roles show only while under 24 hours old, and `android_client` is healthy under 90 minutes and degraded under 240. `GET /health` no longer writes a pulse row, and cron runs never write an `unknown` role, so AKAMAI FUNCTIONS goes offline only when the cron stops.
- **Real darkness** (#188). `/internal/weather-heuristic` computes sunrise, sunset and `is_dark` from the request's coordinates (New York by default), with no network call, instead of always reporting Clear, 25 °C and daylight. Conditions read `unknown` and temperature is null until a weather source is wired.
- `all_clear` no longer treats a past `vacation_mode_until` as a vacation.

### Python MCP server

- **Bridge is loopback-only by default** (#39). The HTTP bridge on port 8080 binds `MECRIS_BRIDGE_HOST`, default `127.0.0.1`; it used to bind every interface. The `/mcp` SSE mount, which offered all 45 tools without credentials, is removed. The default-user fallback applies only to local requests (a loopback peer, a localhost Host and no foreign Origin). Every other caller needs a Pocket ID token whose signature verifies against the JWKS.
- **Truthful pulse** (#346). The system pulse and the health checker use `contracts/pulse_roles.json`. GHOST reads paused unless `MECRIS_GHOST_ENABLED` is set. AKAMAI shows today's refusals and raises one urgent item on a `bad_key` refusal. A process that lost the leader election reads `standby (leader <pid>)` instead of an error, and `/health` reports the leader from the database. Calls to the retired Fermyon app are removed.
- **Claude Ultra subscription** (#345). `budget_tracking` gains `source_type`, `plan` and `monthly_price_usd`. A subscription reads GOOD, ENDING within 14 days of the grant end, or ENDED. The narrator shows one line, such as `Claude: Ultra until <date>, available (…)`, and no `update_budget` nag while the grant runs. Sessions no longer decrement a subscription row, and new databases no longer get the fake $24.96 seed row. `update_budget` accepts the new fields; the tool count stays at 45.
- **Claude plan usage from the Claude Code status line** (#344). `scripts/claude_statusline.py` is a status line command. It reads the `rate_limits` that Claude Code passes to it (the five-hour and seven-day windows), writes them to `~/.claude/usage.json` (`CLAUDE_USAGE_SNAPSHOT` moves it) and prints `5h 16% · wk 24%`. Percentages round half to even, as in every other arm. For the local user, `get_claude_plan_status` and the narrator use that snapshot when it is newer than the latest stored reading, so nobody has to type readings in. Every five minutes the scheduler leader stores the snapshot in Neon as a `claude_code_cli` reading if a window has moved by a point or more since the last stored reading. It stores at most one reading per 15 minutes, except that a change of state or a new week is stored at the next check. Every entrypoint that starts the scheduler (`mcp_server.py`, `mcp_stdio_server.py` and `attic/scripts/simple_main.py`) starts this ingest, and each process checks on every tick whether it is the leader, so only one process stores and a leader handover is honoured. A reading already stored is skipped. Stored readings feed the Beeminder graph (#371) like manual ones. Limits: Claude Code reports no per-model weekly window, so `weekly_fable` stays manual through `record_claude_plan_usage`. The snapshot only updates while Claude Code is making requests, so usage from claude.ai or the desktop app shows up at the next Claude Code response. See `docs/CLAUDE_PLAN_USAGE.md`.
- **One stored Claude reading per user, source and time** (#344). `scripts/migrate_v9_claude_readings_unique.py` (`--dry-run` to preview) removes duplicate readings, keeping the lowest id, and adds a unique index (PostgreSQL 15+); the insert now also has `ON CONFLICT DO NOTHING`, so two leaders storing the same reading at once store it once and push it to Beeminder once. `mecris-go-spin/schema.sql` declares the same index, so a new database gets it from the start.
- **Deterministic tools are not budget-gated** (#351). `get_coaching_insight` and `trigger_language_sync` no longer depend on the API-era `anthropic_api` bucket.
- **The reminder send path matches Spin** (#349, #358). Before `send_reminder_message` sends, a guard applies the same 4-hour any-channel damping and New York daily cap, and refuses to send if it cannot read `message_log`. Rows store `sent_at` as `NOW()` with an explicit channel. A failed WhatsApp attempt is logged as `whatsapp`/`failed`. The console fallback is logged as `console`/`not_sent` and no longer prints the message to stdout. `set_notification_prefs` accepts `max_messages_per_day`.
- **Log hygiene** (#358). The server sets httpx and httpcore logging to WARNING and redacts `auth_token`, `access_token` and `api_key` query values. `MECRIS_LOG_FILE` sets the log path.
- A CRITICAL goal whose road shows nothing due today reads DUE_LATER, and a CRITICAL do-more goal with a zero rate and an unreadable road reads PAUSED. Neither reads DERAILING.
- `mcp` is pinned below 2 in `pyproject.toml` (#319).

### Android (versionCode 41)

- **The phone stops doing the cloud's work** (#368). The background worker no longer calls `trigger-reminders` or `cloud-sync`, the dashboard refresh no longer calls `cloud-sync`, and both routes are gone from the app. FORCE SYNC no longer starts a Clozemaster scrape; the cloud cron and the web app's sync button do.
- **Claude plan and system pulse cards** replace the VIRTUAL BUDGET odometer (#344, #346, #245). The plan card re-checks its data against the clock and reads unknown once the reading is over 24 hours old or its weekly reset has passed. The pulse card shows each modality's status, age and last cron outcome. The dashboard no longer calls `GET /budget`.
- **Pace line** on Arabic and Greek nags (#349), including when Gemini Nano writes the text. It reads `Pace: 42 reviews left today, about 6 an hour to clear them by 10:00 PM.`, or `Pace: 42 reviews left today, due now.` in the last hour before 22:00 and after it.
- **Every shown nag is logged** (#213) to `/internal/log-message` with the bearer, on both fire paths. A failed log never blocks the nag. The old audit call, which sent no bearer, is removed.
- **Backend picker:** Fermyon is gone. Fresh installs, and phones still pointed at Fermyon, use Akamai. `Local (Python: 8080)` stays; see `MECRIS_BRIDGE_HOST`.
- `mcp_server_active` and the weather `temperature` are nullable, so a missing field no longer reads as false or 0.0 °C. The dashboard shows "Temp: unknown".

### Docs and hygiene

- **`contracts/`**: shared truth tables for pulse roles, Claude plan states, nag gates and Spin JSON shapes. pytest, the Rust tests and the Kotlin tests all read them in place. The Claude plan cases cover status line readings: fractional percentages, reset times in UTC compared as instants (a UTC reading and its `-05:00` twin give the same result), a reading minutes old, and no `weekly_fable` window.
- **Repo cleanup** (#348). Root one-offs, images, a third-party PDF and uncollected root tests moved to `attic/`. Build output (`poc/v6-hello/target/`, 798 files) and local databases are untracked and ignored. `tests/test_repo_hygiene.py` guards this.
- **No personal numbers in tracked files** (#358). Two files held a personal phone number; they now use a Twilio test number. `tests/test_no_personal_numbers.py` scans tracked files and allows other dialable numbers only by SHA-256 hash.
- **Docs** (#347). ROADMAP.md is rewritten for November 2026 to May 2027, with the subscription budget and only true security claims. README.md has the matching budget section, ACTIVE_BACKLOG.md is a pointer, and 20 dated root docs moved to `attic/`. `docs/RELEASE_PROCESS.md` no longer tells anyone to install the unsigned release APK, and adds the migration, cron, dry-run and promote-to-Latest steps. The SLSA level reads L2, the Twilio setup guide covers WhatsApp templates, and the workflows README says Postgres 18. `mecris-go-spin/DEPLOYMENT.md` documents the cron-key-only endpoints, the gates, the dry run, where outcomes are recorded, `GET /claude-plan` (including the age rule and the status line reading shape) and `POST /internal/log-message`. The bridge docs say 127.0.0.1. New `docs/CLAUDE_PLAN_USAGE.md` covers the status line setup, the snapshot file and its limits.
- **`scripts/fetch_template_bodies.py`** (#363): a read-only fetcher for the approved WhatsApp template bodies. Not run yet.
- **Renovate** (#218): holds Python below 3.15 and ignores `mcp` majors.

### CI

- `ci.yml` generates the Spin internal API key and master encryption key for each run with `openssl rand -hex 32` and masks them. The hard-coded test master key is gone. New end-to-end tests run against `spin up` and CI's Postgres 18: the gate dry run, cron outcomes and refusals, `message_log` rows, Claude plan and log-message.
- `tests/conftest.py` disables python-dotenv and strips live credentials from the environment before any project import, keeping only a loopback database URL. `MECRIS_TESTS_USE_ENV=1` opts back in. `tests/test_env_isolation.py` checks this. It also points `CLAUDE_USAGE_SNAPSHOT` at a temporary path, so no test reads or stores the developer's real `~/.claude/usage.json`.

### Upgrade notes

Tagging does not deploy anything. Do these in order, after the tag's release workflow has finished:

1. **Migrations**, before the deploy, against Neon. Each reads `NEON_DB_URL`; the first two also load `.env`, the third reads only the environment. All three are additive and safe to run twice:
   1. `scripts/migrate_v9_cloud_observability.py` (`internal_refusals` and the `scheduler_election` outcome columns);
   2. `scripts/migrate_v9_subscription_budget.py` (`budget_tracking.source_type`, `plan`, `monthly_price_usd`);
   3. `scripts/migrate_v9_claude_readings_unique.py --dry-run`, which changes nothing and reports how many duplicate readings it would delete and whether the index exists, then the same command without `--dry-run`, which deletes them and adds the unique index. It needs PostgreSQL 15 or later and refuses an older server before changing anything.

   Only the third has a dry run. The first two take no options: they apply their change whenever they run, with or without `--dry-run`.
2. **Deploy** with `./mecris-go-spin/sync-service/deploy-akamai.sh`. `reminder_standdown_minutes` defaults to 240.
3. **Verify** with `./scripts/verify_spin_deploy.sh`. It is a dry run by default and sends no WhatsApp unless you pass `--live-trigger` (`--no-trigger` is still accepted and does nothing). It sends no keyed request until `/version` reports 0.3.0 with `"dry_run": true` and, when it can read Neon, the burned-key refusals have been counted. Its wrong-key probe is counted as `probe`, so it raises no alert. It does make one real `failover-sync` request, which scrapes Clozemaster if the stats are 100 minutes old or more. The dry run and the `failover-sync` record check cover only users with `autonomous_sync_enabled` (step 7).
4. **Cron**, only after step 3 passes: run `spin aka cron delete failover-sync-edt` and `spin aka cron delete failover-sync-est`, then `./scripts/setup_spin_cron.sh`. It creates `trigger-reminders` at `0 */2 * * *`, which turns cloud reminders back on after the 2026-11-14 pause, and one `failover-sync` at `5 */2 * * *`. `spin aka cron list` prints the key, and the setup script runs it too, so don't paste either output.
5. **Restart** the Claude Desktop and Pi sessions and stop any leftover `mcp_server.py` processes. The bridge then listens on 127.0.0.1 only. If the phone uses `Local (Python: 8080)`, set `MECRIS_BRIDGE_HOST=0.0.0.0`; LAN callers then need a Pocket ID token. To get Claude plan usage from the status line, first add the `statusLine` entry from `docs/CLAUDE_PLAN_USAGE.md` to `~/.claude/settings.json`; servers started before the restart don't read the snapshot. If the narrator does not yet show the Ultra subscription, make one `update_budget` call with `source_type='subscription'`, the plan and the grant dates.
6. **Android:** after three clean cron cycles in `message_log` and the pulse, install versionCode 41 from Android Studio at the tag (debug variant, same debug key, decline any uninstall prompt; the release APK is unsigned). Then tap VERIFY and enter the code: cloud reminders go only to a verified phone.
7. **Autonomous sync:** both cron endpoints act only for users with `autonomous_sync_enabled`. If it was turned off during the pause, turn it back on in the app's profile settings and run `./scripts/verify_spin_deploy.sh` again. If it was never turned off, leave it alone.
8. **Watch** `message_log` for 3 days (metadata only, never message contents): reminders only inside the window, never within 4 hours of another nag, never while the phone's heartbeat is fresh, and never beyond the daily cap. Then promote v0.3.0 to Latest.

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
