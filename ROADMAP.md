# Mecris Roadmap: November 2026 to May 2027

> **Mission**: a personal accountability system that tells the truth about your goals, your budget and itself, and nags only when it should.

## Current Status
- **Version**: v0.2.0 (2026-11-14)
- **Next release**: v0.3.0 (Android versionCode 41 + Spin API), tracked in [#360](https://github.com/kingdonb/mecris/issues/360)
- **Claude**: Ultra plan, a subscription grant running to about 2027-05-13. Usage credits stay off.
- **Cloud reminders**: the `trigger-reminders` cron is paused until v0.3.0 deploys (v0.2.0 sent WhatsApp walk reminders at the wrong hours, see [#369](https://github.com/kingdonb/mecris/issues/369)).

This file is the one current plan. The backlog lives in GitHub issues; [#360](https://github.com/kingdonb/mecris/issues/360) is the epic that orders them. Older plans are archived under `attic/` and `docs/attic/`.

**Guiding principle**: make the dashboard truthful first, then tidy, then build.

---

## Release v0.3.0: prove the cloud arm and tell the truth

Reminders go out only when they should, every cron run leaves a record, every status is real, and the phone shows the Claude plan and review pace.

Decisions already taken:
- **Cloud WhatsApp is a fallback.** Spin stands down while the phone's heartbeat is younger than `reminder_standdown_minutes` (default 240; 0 disables the stand-down).
- **The window comes from your notification prefs**: 14:00 to 17:59 America/New_York, at most 3 a day, counted by send time in New York. America/New_York stays hard-coded (operator ruling, 2026-10-01).
- **Damping**: at most one nag per 4 hours across channels. Local phone nags count toward the 4 hours but not toward the WhatsApp daily cap.
- **The cloud owns periodic language sync.** The phone stops calling `trigger-reminders` and `cloud-sync`.
- **Android health**: healthy under 90 minutes since the last heartbeat, degraded under 240.
- **Phone**: a Claude plan card replaces the VIRTUAL BUDGET odometer (the web keeps it).

Pull requests, in merge order: the loopback-only bridge (#39), shared contracts, repo hygiene and docs (#347, #348, #218), the Spin cloud arm (#183, #368, #349 damping), the Python MCP server (#346, #345, #351), Android (#344, #349, #213), Spin status (#344, #213, #346, #188), then the release itself.

Deploy and verify, in order: additive migrations (with the owner's OK), `deploy-akamai.sh`, recreate the crons, a dry-run verify, 3 clean cron cycles, then install VC 41 on the phone; promote the release to Latest only after a 3-day `message_log` watch (see `docs/RELEASE_PROCESS.md`).

---

## Phase 1: truthful status (Nov to Dec 2026)
- [#344](https://github.com/kingdonb/mecris/issues/344) Claude plan usage telemetry across MCP, Spin, Android and Pi.
- [#345](https://github.com/kingdonb/mecris/issues/345) Model the Ultra subscription; end the stale-period false alarm.
- [#346](https://github.com/kingdonb/mecris/issues/346) Quiet the paused ghost, retire dead modalities (Fermyon, boris-fiona-walker), on-demand Akamai.
- [#183](https://github.com/kingdonb/mecris/issues/183) Prove each Akamai cron run by its side effects.

## Phase 2: tidy (Nov 2026 to Jan 2027)
- [#347](https://github.com/kingdonb/mecris/issues/347) One current roadmap; dated docs archived under `attic/`.
- [#348](https://github.com/kingdonb/mecris/issues/348) Repo root cleanup; build output untracked; a CI guard keeps it that way.
- [#218](https://github.com/kingdonb/mecris/issues/218) Renovate rules: Python held below 3.15, mcp majors ignored until the v2 migration.

## Phase 3: build (Jan to May 2027)
- [#349](https://github.com/kingdonb/mecris/issues/349) Review Pump velocity in nags, plus 1-per-4h damping (damping ships in v0.3.0; WhatsApp wording waits for #363).
- [#363](https://github.com/kingdonb/mecris/issues/363) WhatsApp template catalog: approved bodies in the repo, then purpose-built templates.
- [#350](https://github.com/kingdonb/mecris/issues/350) Smarter nag timing: time of day, urgency, success patterns.
- [#351](https://github.com/kingdonb/mecris/issues/351) Reserve budget so essential nags survive low balances.
- [#352](https://github.com/kingdonb/mecris/issues/352) Deterministic daily morning briefing in Obsidian.
- [#353](https://github.com/kingdonb/mecris/issues/353) Automatic `ask_mecris` indexing and an eval set.
- [#354](https://github.com/kingdonb/mecris/issues/354) Obsidian commitments to Beeminder, opt-in per goal.
- [#355](https://github.com/kingdonb/mecris/issues/355) Split `mcp_server.py` behind a pinned tool surface, together with the mcp v2 migration (#319).

## Security and supply chain (any phase)
- [#358](https://github.com/kingdonb/mecris/issues/358) PII encryption audit of Neon tables and logs.
- [#357](https://github.com/kingdonb/mecris/issues/357) SLSA Build Level 3.
- [#356](https://github.com/kingdonb/mecris/issues/356) Secret Manager hardening.

## Gated
- [#359](https://github.com/kingdonb/mecris/issues/359) The ghost (mecris-bot) stays off until its spend can be capped with guarantees and it fails closed.

---

## Budget

Claude work runs on the **Ultra plan**, a subscription grant that started 2026-11-13 and runs to about 2027-05-13. It is not a prepaid API balance, so there is no dollar figure to burn down. What matters is plan usage (session and weekly limits) and the grant's end date. **Usage credits stay off**; nothing on this roadmap turns them on.

How Mecris tracks it (#345, landing in v0.3.0):
- `budget_tracking` gets a `source_type`: `api_credit` (the old model), `subscription` or `retired`. A subscription row is not decremented by usage.
- The budget reads **GOOD** while the grant runs, **ENDING** within 14 days of the end date, **ENDED** after it, and **RETIRED** for a retired source, which raises no alerts.
- The narrator shows one phrase built from the grant and the latest plan reading, for example `Claude: Ultra until 2027-05-13, available (3% weekly, resets Mon 4:00 AM)`. There is no `update_budget` nag while the grant is live, one recommendation at ENDING and one urgent item at ENDED.
- Plan readings are recorded with `record_claude_plan_usage` and read with `get_claude_plan_status`; a reading older than 24 hours shows as unknown.
- The plan's price is not hard-coded anywhere.

Other spend is tracked separately: the Helix wallet balance (`helix-ml` odometer, `docs/HELIX_BALANCE_SYNC.md`) and the Groq odometer. Both governors are described in `docs/HOW_MECRIS_WORKS.md`.

---

## Security: what is true today

Only claims the code backs up:
- **Spin (Rust) arm**: tokens, credentials and the phone number are encrypted with AES-256-GCM, and it refuses to store a phone number it cannot encrypt. Location (latitude and longitude) is stored in plaintext. The Twilio webhook checks the request signature. The cron endpoints (`/internal/trigger-reminders`, `/internal/failover-sync`) accept the private `INTERNAL_API_KEY` (header or `key` query parameter) **or any signed-in PocketID bearer**; v0.3.0 is to make them cron-key only. The other `/internal/*` routes take a signed-in bearer, except `/internal/weather-heuristic`, which is open.
- **Python arm**: encryption still **fails open**. `try_encrypt` returns plaintext when `MASTER_ENCRYPTION_KEY` is missing, and the legacy plaintext `users.beeminder_user` column is still read and written. Fixing this is the #358 remainder.
- **MCP bridge**: in v0.2.0 it listens on all interfaces on port 8080; v0.3.0 makes it loopback-only (#39).
- **Builds**: release assets carry SLSA v1 provenance from GitHub-hosted runners, which is **Build Level 2**. Level 3 is #357. The release APK is **unsigned**; see `docs/RELEASE_PROCESS.md` for how to install safely.
- **Repo**: a CI test rejects personal phone numbers in tracked files. Numbers committed before it are still in git history; rewriting history is the owner's decision.

---

## Later (no dates)
- Knowledge base and RAG over the docs and the Obsidian vault (#353 is the first step).
- Chrome bookmarks as context.
- Local inference through Ollama with a cloud fallback router (#203).
- Logic moving from Python into Rust/Wasm components (#142, #154).
