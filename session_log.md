# MCP Server Debugging Session Log - MECRIS

This document summarizes the collaborative debugging session to establish a functional MCP (Machine Context Provider) server for Mecris, integrated with the Gemini CLI. The session involved resolving a series of initialization and tool registration errors within `mcp_server.py`.

## 1. Initial Server Initialization Failure (`NoneType` Error)

**Problem:** The MCP server failed to initialize, reporting a `WARNING:root:Failed to validate request: 'NoneType' object has no attribute 'capabilities'`. This indicated an issue with the server's handling of the initial `initialize` JSON-RPC request from the Gemini CLI, specifically concerning the `capabilities` field within the request parameters.

**Initial Attempted Solution:** Based on an assumption about the `mcp-python-sdk`'s internal structure, a custom asynchronous handler (`handle_initialize`) was added to `mcp_server.py` and assigned to `server._initialize_handler`. This handler was designed to return basic server information, expecting the SDK to correctly process the `capabilities`.

## 2. Invalid Request Parameters During Discovery (`-32602` Error)

**Problem:** Despite the custom `initialize` handler, the CLI reported `MCP error -32602: Invalid request parameters` during the discovery phase. Further, it was noted that the server's startup log (`logger.info("Starting Mecris MCP Server in stdio mode...")`) was interfering with the JSON-RPC handshake by printing to `stdout`.

**Solution:**
*   The previous `handle_initialize` function and its assignment were removed, as they were not the correct approach.
*   The `main()` function was updated to leverage `mcp.server.models.InitializationOptions` to explicitly define the server's capabilities for the `server.run()` call.
*   `server.get_capabilities()` was used to retrieve the actual capabilities, which were then passed into `InitializationOptions`.
*   The startup log message was changed from `logger.info` to `logger.error` to ensure it was directed to `sys.stderr`, preventing corruption of the `stdout` JSON-RPC stream.

## 3. Correcting `Server.get_capabilities()` Signature (`TypeError`)

**Problem:** After the previous changes, a `TypeError: Server.get_capabilities() is missing 2 required positional arguments: notification_options and experimental_capabilities` was encountered. This indicated that the `get_capabilities()` method from the `mcp-python-sdk` required specific arguments.

**Solution:**
*   `NotificationOptions` was imported from `mcp.server`.
*   The `server.get_capabilities()` call in `main()` was updated to explicitly pass `notification_options=NotificationOptions()` and `experimental_capabilities={}` as required arguments.

## 4. Resolving Pydantic Validation for `InitializationOptions` (`ValidationError`)

**Problem:** A `pydantic_core._pydantic_core.ValidationError` occurred, stating that the `InitializationOptions` object was missing required fields: `server_name` and `server_version`.

**Solution:**
*   The `InitializationOptions` constructor in `main()` was updated to include `server_name="mecris"` and `server_version="0.2.0"` (or a preferred version) along with the `capabilities`.

## 5. Refactoring to `FastMCP` for Tool Registration ("No prompts, tools, or resources found")

**Problem:** The server was connecting, but the CLI reported: "No prompts, tools, or resources found on the server." This indicated a fundamental issue with how tools were being registered and made available to the MCP client. It was also clarified that the `Server` object being used did not have a `.tool` attribute for decorator-based registration, suggesting an incorrect class choice or usage pattern.

**Solution:**
*   The `mcp_server.py` file was refactored to use `FastMCP` for a simpler and more correct implementation of tool registration.
*   Imports for `Server`, `NotificationOptions`, `stdio_server`, and `InitializationOptions` were replaced with `from mcp.server.fastmcp import FastMCP`.
*   The server initialization was changed from `server = Server("mecris")` to `mcp = FastMCP("mecris")`.
*   All tool functions, which were previously defined in a `server.tools` list and called via a `_call_tool_handler`, were updated to use the `@mcp.tool()` decorator directly above their definitions. This involved removing the `server.tools` list and the `call_tool` function.
*   The `main()` function was entirely removed and replaced with a simplified entry point: `if __name__ == "__main__": mcp.run()`, which automatically handles the stdio server setup.

## 6. Final `FastMCP.tool()` Argument Correction (`TypeError: input_schema`)

**Problem:** After refactoring to `FastMCP`, a `TypeError: FastMCP.tool() got an unexpected keyword argument 'input_schema'` was encountered. This indicated that `FastMCP` automatically infers the tool's input schema from the decorated function's signature and does not accept `input_schema` as a manual argument in the decorator.

**Solution:**
*   The `input_schema` argument was removed from all `@mcp.tool()` decorators across all 14 tool functions.

**Outcome:** With these iterative fixes, the Mecris MCP server should now correctly initialize, register its tools, and communicate effectively with the Gemini CLI.
---

## 2026-03-26 — mecris-bot goes live, skills loop designed

**Planned**: Get the autonomous bot working end-to-end and test it against a real upstream PR.

...

## 2026-03-31 — Post-Mortem & Fix: Greek Data Corruption (ellinika)

**Planned**: Investigate reports of "spurious" Greek Beeminder data points for the `ellinika` goal; find the source and provide a fix plan.

**Done**: 
- Root cause identified as a category error: treating the `ellinika` odometer/cumulative goal as a backlog-tracking snapshot. 
- **Implemented Fix**: Removed Greek Beeminder push mappings from `scripts/clozemaster_scraper.py` (Python), `services/language_sync_service.py` (Python), and `mecris-go-spin/sync-service/src/lib.rs` (Rust/Failover).
- Updated `tests/test_greek_slug.py` to ensure Greek is no longer automated.
- Published full post-mortem in `docs/postmortems/2026-03-31-greek-data-corruption.md`. 
- Added `GEMINI.md` directive #6 (Goal Type Awareness) to prevent recurrence.

**Next**: Catch up `yebyen/main` with these fixes and redeploy Spin components to Fermyon Cloud.

## 2026-03-31 — Fix Review Pump UX bug: remaining target and unmet goal sorting

**Planned**: Fix Review Pump UX bug where "Target Flow" did not account for completions, and languages were not sorted by urgency. (yebyen/mecris#47)

**Done**:
- Modified `ReviewPump.get_status` (Python) to subtract `daily_completions` from `target_flow_rate` and added `goal_met` boolean.
- Modified `ReviewPump` (Rust/Spin) to mirror the Python logic for consistency across all layers.
- Updated `mcp_server.py` to sort `get_language_velocity_stats` results: unmet goals (`goal_met=False`) are surfaced first, then sorted by remaining `target_flow_rate` descending.
- All 22+ review pump tests (Python) pass.
- Verified fix with dry-run: Greek with 0 debt/liability now shows `target_flow_rate: 0` and `goal_met: True`, ensuring Arabic (untouched) is surfaced first.

**Next**: Permanent fixes for Greek data corruption and Review Pump UX bug are now implemented, committed, pushed to `yebyen/main`, and deployed to Fermyon Cloud.

## 2026-03-31 — Phase 1.5b: componentize-py WASM component for arabic_skip_counter

**Planned**: Set up componentize-py toolchain, write WIT interface for arabic_skip_counter, produce a `.wasm` artifact in `mecris-go-spin/arabic-skip-counter/`. (yebyen/mecris#48)

**Done**:
- Installed `componentize-py 0.21.0` via pip (24MB wheel, works in GitHub Actions runner).
- Created `mecris-go-spin/arabic-skip-counter/wit/world.wit`: exports `count-arabic-reminders(neon-url: string, user-id: string, hours: u32) -> u32`.
- Generated Python bindings via `componentize-py bindings` (produced `wit_world/` stub package).
- Discovered key naming convention: concrete `WitWorld` class in `app.py` must NOT inherit from the generated abstract Protocol — it must be a fresh concrete class with the same name. This resolves the `AssertionError: TypeError: Can't instantiate abstract class WitWorld` build error.
- Built `arabic-skip-counter.wasm` (43MB, CPython + httpx embedded) — valid WebAssembly component.
- Added `[component.arabic-skip-counter]` to `spin.toml` with build command and `allowed_outbound_hosts = ["https://*.neon.tech"]`.
- Added `mecris-go-spin/arabic-skip-counter/.gitignore` to exclude WASM artifacts and generated stubs.
- Wrote 6 unit tests in `tests/test_arabic_skip_counter_component.py` — all pass.
- 24/24 total tests pass (no regressions).

**Skipped**: HTTP trigger wrapper (Phase 1.6) — current WIT is a function-export world, not an HTTP component. Deliberate: validates the componentize-py pipeline first; HTTP route is the next increment. `spin call` invocation not tested (spin CLI not installed in runner).

**Next**: Open sync PR to kingdonb/mecris carrying Phase 1.5b. Then Phase 1.6: HTTP wrapper for `/internal/arabic-skip-count` route.

## 2026-03-31 — Phase 1.6: HTTP trigger wrapper for arabic-skip-counter

**Planned**: Add HTTP trigger wrapper for `arabic-skip-counter` — rewrite WIT to WASI HTTP incoming-handler, implement IncomingHandler class, add `neon_db_url` Spin variable, register `GET /internal/arabic-skip-count` route. (yebyen/mecris#50)

**Done**:
- Opened sync PR kingdonb/mecris#161 (yebyen→kingdonb, Phase 1.5b WASM work — pending review).
- Rewrote `world.wit` to WASI HTTP incoming-handler world (wasi:http/incoming-handler@0.2.0), replacing function-export world.
- Rewrote `app.py`: added `_parse_query_params()`, `_json_response()`, `_error_json()` helper functions; added `IncomingHandler` class using `spin_sdk` (guarded with `try/except ImportError` for CI testability).
- Added `spin-sdk>=3.0.0` to `requirements.txt`.
- Updated `spin.toml`: added `[[trigger.http]]` for `/internal/arabic-skip-count`, added `neon_db_url` to `[variables]`, bound variable in `[component.arabic-skip-counter.variables]`, changed build command to `spin py2wasm app -o arabic-skip-counter.wasm`.
- Replaced 6 `WitWorld` tests with 16 helper-function tests. Total suite: 34/34 passing (up from 24).
- Committed at `6e93e9b`.

**Skipped**: WASM build (`spin py2wasm`) and live HTTP validation (`curl`) — `spin` CLI and `componentize-py` binary not available in CI runner. Also skipped: verify `request.uri` attribute name in spin_sdk>=3.0.0 (may be `request.url`); document componentize-py conventions in `docs/LOGIC_VACUUMING_CANDIDATES.md`.

**Next**: In deployment environment: `pip install -r requirements.txt && spin py2wasm app -o arabic-skip-counter.wasm`, then `curl "http://localhost:3000/internal/arabic-skip-count?user_id=yebyen&hours=24"`. Confirm `{"skip_count": <int>}` response. Open Phase 1.6 sync PR to kingdonb once WASM validates.

## 2026-03-31 — Document componentize-py WitWorld/IncomingHandler conventions

**Planned**: Add "componentize-py Class Naming Conventions" section to `docs/LOGIC_VACUUMING_CANDIDATES.md` covering WitWorld (function-export world) and IncomingHandler (HTTP world) patterns, including try/except ImportError CI guard. (yebyen/mecris#51)

**Done**:
- Added 65-line section to `docs/LOGIC_VACUUMING_CANDIDATES.md` under Candidate 3 covering:
  - Function-export world: fresh concrete `WitWorld` class, no inheritance from generated Protocol.
  - HTTP world: `IncomingHandler(spin_sdk.http.IncomingHandler)`, `try/except ImportError` guard, all logic outside the class for CI testability.
  - `request.uri` attribute note (verify against installed spin-sdk version).
  - Build command reference table for both world types.
  - Rationale: why names are fixed (toolchain binding shim lookup by class name).
- Committed at `53e65b0`. Plan issue yebyen/mecris#51 closed.
- NEXT_SESSION.md updated: componentize-py convention item moved from Pending to Verified.

**Skipped**: WASM build/live test (blocked — no `spin` CLI in CI). Phase 1.6 PR to kingdonb (gated on WASM validation; existing PR #161 carries both 1.5b+1.6 code).

**Next**: WASM build validation in a deployment environment with `spin` + `componentize-py 0.21.0`. Then confirm kingdonb/mecris#161 review/merge path.

## 2026-04-01 — Update PR #161 to reflect Phase 1.5b + 1.6 content

**Planned**: Update kingdonb/mecris#161 title and description to accurately reflect that it carries Phase 1.5b WASM component AND Phase 1.6 HTTP trigger wrapper, since PR was opened before Phase 1.6 commits landed. (yebyen/mecris#52)

**Done**:
- Updated PR #161 title: `feat(phase-1.5b+1.6): arabic_skip_counter WASM component + HTTP trigger wrapper`.
- Rewrote PR body: Phase 1.5b and 1.6 deliverables listed separately, 34/34 test plan checklist, "Next" updated to Phase 1.7 WASM validation.
- Used `gh api --method PATCH` (REST) rather than `gh pr edit` — `gh pr edit` fails with GITHUB_CLASSIC_PAT (repo-only scope) due to `read:org` requirement in GraphQL.
- Noted token scope workaround in NEXT_SESSION.md Infrastructure Notes.

**Skipped**: Nothing — task was tight and complete. WASM build validation still blocked (no `spin` CLI in CI runner).

**Next**: WASM build validation in deployment environment. `spin py2wasm app -o arabic-skip-counter.wasm` in `mecris-go-spin/arabic-skip-counter/`, then live curl test. Await kingdonb/mecris#161 review/merge.

## 🏛️ 2026-04-01 — Health report: orientation only, no unblocked work

**Planned**: Document Phase 1.6/1.7 blocked state and archive cleanly. (yebyen/mecris#53)

**Done**:
- Ran full orient: confirmed yebyen/mecris 7 commits ahead of kingdonb via open PR #161 (awaiting review).
- Confirmed no labeled issues (needs-test/pr-review/bug) in either repo.
- Confirmed no bot-accessible code work unblocked: Phase 1.7 requires live Spin CLI (unavailable in CI), issue #122 is Android UI work, issue #132 needs live Neon/Spin verification.
- Opened health report plan issue yebyen/mecris#53 (closed at archive).
- Updated NEXT_SESSION.md to reflect 2026-04-01 orientation status.

**Skipped**: Code work — nothing unblocked. WASM build still blocked on CI environment. PR #161 still awaiting kingdonb review.

**Next**: WASM build validation in a deployment environment with `spin` + `componentize-py 0.21.0`. `spin py2wasm app -o arabic-skip-counter.wasm` in `mecris-go-spin/arabic-skip-counter/`, then live curl test. Await kingdonb/mecris#161 review/merge.

## 2026-03-31 — Fix: arabic-skip-counter WASM build and Documentation Update

**Planned**: Resolve the `AttributeError: module 'app' has no attribute 'handle_request'` during the `spin py2wasm` build and update project documentation.

**Done**:
- **Fixed `arabic-skip-counter` WASM build**: Added the `handle_request` top-level entry point to `mecris-go-spin/arabic-skip-counter/app.py`, as required by the `spin py2wasm` toolchain.
- **Verified WASM build**: Successfully compiled `arabic-skip-counter.wasm` using the `spin py2wasm` plugin.
- **Updated `GEMINI.md`**: Added a new mandate: **NO RECURSIVE GLOBAL GREP**. This prevents performance issues and unnecessary context usage in large directories.
- **Updated `docs/SETUP_GUIDE.md`**: Added a dedicated section for Playwright installation (`.venv/bin/python3 -m playwright install`) to resolve "missing browser binaries" errors during automated scrapers.
- **Documented Groq Scraping Decision**: Added a reference to the [Groq community thread](https://community.groq.com/t/add-api-endpoint-to-fetch-billing-and-usage-data/378) in `fetch_groq_usage.py` and `claude_api_budget_scraper.py` to explain the intentional avoidance of scraping Groq due to Google SSO and the lack of an official API.
- **Verified `trigger_language_sync`**: Confirmed that the Clozemaster-to-Beeminder sync is fully functional after the Playwright installation.
- **Merged `yebyen/main`**: Pulled and reviewed the latest changes from the autonomous worker, resolving the WASM build blocker.

**Next**: Push all changes to `origin/main` and confirm the deployment status in Fermyon Cloud.

## 🏛️ 2026-04-01 — Test coverage audit for kingdonb review-pump + language-velocity fixes

**Planned**: Audit test coverage for 5 commits kingdonb pushed today (dc2e1fe→f62ad68): review-pump goal_met refinement, GREEK canonical goal, language-velocity safebuf/beeminder_slug columns. Add targeted pytest cases. (yebyen/mecris#55)

**Done**:
- Read all 5 kingdonb commits and identified 3 coverage gaps.
- Added `test_goal_met_when_debt_rounds_to_zero_target_with_aggressive_multiplier` — covers fix 5cb1397: small debt with multiplier > 1.0 rounds target to 0, goal_met=True.
- Added `test_goal_met_false_in_maintenance_mode_with_outstanding_debt` — regression guard for maintenance-mode debt path.
- Added `test_get_language_stats_includes_beeminder_slug_and_safebuf` — covers fix f62ad68: 8-column DB query returns new fields.
- Fixed pre-existing wrong assertion in `test_system_overdrive` (target_flow_rate is remaining work, not total target).
- Committed as ec4d578. 13/13 pass in the two touched test files.

**Skipped**: GREEK canonical test — Rust sync-service (9d90f69) cannot be unit-tested from Python. No open issues remain on either repo. Phase 1.7 WASM build still blocked on CI environment.

**Next**: WASM build validation in a deployment environment with `spin` + `componentize-py 0.21.0`. `spin py2wasm app -o arabic-skip-counter.wasm` in `mecris-go-spin/arabic-skip-counter/`, then live curl test.

## 🏛️ 2026-04-01 — Session 2: Propose test coverage upstream via kingdonb/mecris#163

**Planned**: Open health report, propose the 2 ahead commits (test coverage for goal_met edge cases + beeminder_slug/safebuf) as a PR to kingdonb/mecris if clean, then archive. (yebyen/mecris#56)

**Done**:
- Ran full orient: yebyen/mecris 2 commits ahead of kingdonb (ec4d578 test coverage + cf4af18 archive). Zero open issues on both repos. All WASM tasks blocked on live environment.
- Confirmed ec4d578 is clean for upstream: only `tests/test_neon_sync_checker.py` and `tests/test_review_pump.py` — no yebyen-private content.
- Created branch `test/review-pump-neon-coverage-2026-04-01` in yebyen/mecris at ec4d578 and pushed.
- Opened PR kingdonb/mecris#163 with test coverage for goal_met edge cases + beeminder_slug/safebuf columns.

**Skipped**: Nothing unblocked was skipped. WASM build validation still requires live Spin CLI unavailable in CI. Issue #122 (Android) and Issue #132 (live Spin/Neon) remain out of scope for bot.

**Next**: Check if kingdonb/mecris#163 has been reviewed/merged. If merged, confirm yebyen/mecris sync state. WASM build validation in a deployment environment with `spin` + `componentize-py 0.21.0`.

## 🏛️ 2026-04-01 — Session 3: pr-test fork-PR bug diagnosis (partial)

**Planned**: Dispatch pr-test against kingdonb/mecris#163 and post results as a comment. (yebyen/mecris#57)

**Done**:
- Ran full orient: PR #163 still open, no labels, no CI run, no upstream activity since session 2.
- Dispatched pr-test twice (runs #23863414611 and #23863517252). Both failed at "Fetch and merge upstream PR branch" step.
- Root cause confirmed: `pr-test.yml` always tries `git merge upstream/${PR_BRANCH}`. PR #163 head is on yebyen/mecris (fork), so the branch doesn't exist in `upstream` (kingdonb/mecris) — it's in `origin`.
- Fix identified: detect `head.repo.full_name` from PR API; use `git fetch origin ${PR_BRANCH}` if head is yebyen. The checkout's `fetch-depth: 0` already fetches all origin branches, so it's available.
- Committed fix locally as 412f032 but could not push: both PATs lack `workflow` scope required by GitHub to modify `.github/workflows/` files. Reverted 412f032 to avoid breaking the mecris-bot.yml push step.
- Posted blocker comment on kingdonb/mecris#163 explaining the token scope issue.

**Skipped**: Deploying the pr-test fix — blocked on `workflow` scope in MECRIS_BOT_CLASSIC_PAT. PR #163 cannot be auto-tested until kingdonb updates the secret.

**Next**: Ask kingdonb to update MECRIS_BOT_CLASSIC_PAT to include `repo + workflow` scopes. Once done, re-run `/mecris-pr-test 163` which will pick up the fix in NEXT_SESSION.md.

## 🏛️ 2026-04-01 — Session 4: Nag Ladder Tier field + Tier 3 WhatsApp High Urgency detection (complete)

**Planned**: Add explicit `tier` (1/2/3) to all `check_reminder_needed()` return dicts, add Tier 3 detection for goals with runway < 2 hours, update `nag eval` CLI output. (yebyen/mecris#58)

**Done**:
- Orient: PR #163 still open, no `needs-test`/`pr-review` labels, pr-test fix still blocked on workflow-scope token. Identified kingdonb/mecris#139 (Nag Ladder) as highest-value tractable work.
- Opened plan yebyen/mecris#58 before touching code.
- Added `_parse_runway_hours()` to `ReminderService`: parses "N hours" format only; "N days" returns 999 to avoid false Tier 3 triggers.
- Added Tier 3 check at top of `check_reminder_needed()`: CRITICAL goals with `runway < 2.0 hours` → `beeminder_emergency_tier3` at `tier: 3`, 1h cooldown.
- Added `tier: 1` to `walk_reminder`, `arabic_review_reminder`, `beeminder_emergency`.
- Added `tier: 2` to `arabic_review_escalation`, `momentum_coaching`.
- Updated `nag eval` CLI to show "Tier: N" alongside send/no-send status.
- Added 4 new tests: tier 1 on walk_reminder, tier 2 on escalation, tier 3 on "1.5 hours" runway, no tier 3 for "0 days".
- 17/17 reminder_service tests pass; 29/29 target tests pass. Committed c4857ba.

**Skipped**: Tier 2 generalization (freeform Claude for any goal type after idle window) — needs acknowledgement tracking design first. Documented in NEXT_SESSION.md Pending.

**Next**: Check if kingdonb/mecris#163 has been reviewed/merged. If MECRIS_BOT_CLASSIC_PAT workflow scope is granted, deploy pr-test fix and re-run /mecris-pr-test 163. Otherwise: design Tier 2 acknowledgement tracking as a sub-issue of #139.

## 🏛️ 2026-04-01 — Session 5: Nag Ladder Tier 2 time-based escalation (complete)

**Planned**: Add Tier 2 time-based escalation to `ReminderService` — any Tier 1 result escalates to Tier 2 (`use_template: False`) after `TIER2_IDLE_HOURS` idle, using `message_log` history via `log_provider`. (yebyen/mecris#59)

**Done**:
- Orient: PR #163 still open, no upstream activity, pr-test fix still token-blocked. Identified Tier 2 generalization as highest-value unblocked work.
- Opened plan yebyen/mecris#59 with full design notes before touching code.
- Added `TIER2_IDLE_HOURS = 6.0` module constant to `services/reminder_service.py`.
- Added `_apply_tier2_escalation()` async helper: skips Tier 2/3 results, uses existing `_get_hours_since_last()` (999.0 sentinel for no history/no provider → safe no-op).
- Applied escalation at all 3 Tier 1 return sites: walk_reminder, beeminder_emergency, arabic_review_reminder.
- Added 5 new tests covering: escalation fires after 6h (beeminder + walk), stays Tier 1 under 6h, no escalation without log_provider, Tier 3 unaffected.
- 22/22 reminder_service tests pass. Committed 3a34478.

**Skipped**: Acknowledgement tracking / explicit reset mechanism for escalation state — implicit reset (goal exits CRITICAL → condition never fires) may be sufficient. Needs design decision before next coding slice.

**Next**: Decide if implicit reset is sufficient for Tier 2 ack tracking (document decision as sub-issue of kingdonb/mecris#139). Then either: deploy pr-test fix if MECRIS_BOT_CLASSIC_PAT workflow scope is granted, or continue with Tier 2 ack tracking design.

## 🏛️ 2026-04-01 — Session 6: Removal of undeliverable SMS path (complete)

**Planned**: Remove all SMS fallback logic and Tier 3 SMS emergency path due to missing A2P 10DLC registration. Redefine Tier 3 as WhatsApp High Urgency.

**Done**:
- Disabled `send_sms` in `twilio_sender.py` with an error log explaining the A2P blocker.
- Removed SMS fallback from `smart_send_message` in `twilio_sender.py`.
- Renamed `sms_emergency` to `beeminder_emergency_tier3` in `ReminderService`.
- Updated Tier 3 logic to use freeform WhatsApp messages for high-urgency alerts (< 2h runway).
- Updated all unit tests in `tests/test_reminder_service.py` to reflect the new WhatsApp-only reality for Tier 3.
- Verified all 22 `reminder_service` tests pass.
- Updated `NEXT_SESSION.md` and `session_log.md` to remove SMS references.

**Skipped**: None.

**Next**: Merge `review-bot-changes` to `main` and deploy.

## 🏛️ 2026-04-01 — Session 7: Tier 2 escalation reset semantics — implicit reset proven (complete)

**Planned**: Determine whether Tier 2 escalation resets correctly via implicit means or requires explicit `last_acknowledged` tracking; document with a test; implement only if gap found. (yebyen/mecris#61)

**Done**:
- Orient: discovered PR #163 is MERGED (was listed as open in session 5 notes). Repos now fully in sync at b28285e. Zero open issues on either repo.
- Opened plan yebyen/mecris#61 before touching code.
- Read `reminder_service.py` fully; traced escalation reset for beeminder_emergency, walk_reminder, and arabic_review_reminder paths.
- Design decision: **implicit reset is sufficient** — two mechanisms: (1) condition exit (goal not CRITICAL, walk done) skips code path entirely; (2) Tier 2 send logs same type, resetting hours_since_last, so next fire (4h later) sees 4h < TIER2_IDLE_HOURS=6h → Tier 1.
- Posted full analysis to yebyen/mecris#61 as a comment before coding.
- Added `test_tier2_escalation_resets_after_tier2_message_sent`: proves beeminder Tier 2 resets after send.
- Added `test_tier2_walk_escalation_implicit_reset_when_user_walks`: proves walk Tier 2 cannot stick after activity.
- 25/25 reminder_service tests pass. Committed 354cae4.

**Skipped**: No explicit `last_acknowledged` implementation — analysis showed it is not needed. Tier 2 message content (what does a Tier 2 walk_reminder actually say?) is deferred.

**Next**: If MECRIS_BOT_CLASSIC_PAT workflow scope is granted, deploy pr-test fork-PR fix. Otherwise: Tier 2 freeform message content design (what coaching text does the escalated walk_reminder send?).

## 🏛️ 2026-04-02 — Session 9: Ghost Presence Detection — ghost.presence module (complete)

**Planned**: Implement `presence.lock`-based coordination for autonomous ghost sessions so they can signal aliveness and yield to human operators. (yebyen/mecris#62)

**Done**:
- Orient: NEXT_SESSION.md identified Goal 1 Phase 1 (Ghost Presence Detection) as highest priority. No issues tagged needs-test/pr-review/bug on either repo. yebyen in sync with kingdonb.
- Opened plan yebyen/mecris#62 before touching code.
- Discovered `cli/main.py::run_presence()` already had inline presence logic (check/take/release) but no importable module and no tests.
- Created `ghost/__init__.py` and `ghost/presence.py` with: `acquire_lock()`, `release_lock()`, `check_presence()`, `presence_lock()` context manager, `PresenceStatus` dataclass, configurable TTL (default 30 min).
- Created `tests/test_ghost_presence.py` with 16 tests: acquire creates file, writes timestamp, release removes file, returns True/False correctly, roundtrip, no-lock means no human, fresh lock means human present, stale lock means human gone, custom TTL, lock path in status, context manager creates/removes/yields path/releases on exception/detects concurrent session.
- Refactored `cli/main.py::run_presence()` to import from `ghost.presence` — no behavior change, logic centralized.
- All 16 tests pass. Committed 3f06f2b.

**Skipped**: Archivist ghost session wiring (Phase 2) — out of scope for this plan issue. Carried forward.

**Next**: Create `ghost/archivist.py` — cron-invocable script that checks presence, calls a pulse MCP function, and logs to `logs/ghost_archivist.log`.

## 🏛️ 2026-04-02 — Session 10: Ghost Archivist — ghost.archivist module (complete)

**Planned**: Create `ghost/archivist.py` — cron-invocable presence-aware pulse logger. (yebyen/mecris#63)

**Done**:
- Orient: NEXT_SESSION.md identified Ghost Archivist (Goal 1 Phase 2) as highest priority. No issues tagged needs-test/pr-review/bug on either repo. yebyen is 2 commits ahead of kingdonb.
- Opened plan yebyen/mecris#63 before touching code.
- Read `ghost/presence.py` and `mcp_server.py` to understand available interfaces; confirmed `/health` and `/narrator/context` HTTP endpoints exist on FastAPI at localhost:8000.
- Created `ghost/archivist.py` with: `run()` (main entrypoint), `pulse()` (HTTP health probe with offline fallback), `_write_log()` (ISO-8601 UTC append). Env var overrides for lock path, log path, and MCP URL.
- Created `tests/test_archivist.py` with 10 tests: pulse online/offline/timeout, YIELD path, PULSE online path, PULSE offline path, log dir creation, return codes, ISO timestamp.
- All 10 tests pass. Committed e8ef739.
- Smoke test verified: `python ghost/archivist.py` logs `[PULSE] mcp=offline` correctly when server is not running.

**Skipped**: Cron/scheduler registration (Phase 3) — out of scope for this plan issue. Carried forward.

**Next**: Wire `ghost/archivist.py` into `scheduler.py` as a recurring cron job; verify `logs/ghost_archivist.log` accumulates entries autonomously.

## 🏛️ 2026-04-02 — Session 11: Ghost Archivist — cron scheduler integration (complete)

**Planned**: Register `ghost/archivist.run()` as a 15-minute interval leader job in `scheduler.py`. (yebyen/mecris#64)

**Done**:
- Orient: NEXT_SESSION.md identified Goal 1 Phase 3 (Cron Integration) as highest priority. No issues tagged needs-test/pr-review/bug on either repo.
- Opened plan yebyen/mecris#64 before touching code.
- Read `scheduler.py` in full to understand the leader-job pattern (`_start_leader_jobs` / `_stop_leader_jobs`).
- Added `_global_archivist_job(user_id)` to `scheduler.py`: checks `is_leader`, imports and calls `ghost.archivist.run()`, catches all exceptions and logs errors.
- Registered in `_start_leader_jobs` with `minutes=15`, `id=auto_archivist_{user_id}`; registered removal in `_stop_leader_jobs`.
- Added `TestGlobalArchivistJob` to `tests/test_archivist.py` with 3 tests: leader fires run(), non-leader skips, exceptions are caught and logged. Used autouse fixture to mock psycopg2/apscheduler at import time.
- Updated `tests/test_scheduler_election.py` leader job counts from 4→5 (adds/removes).
- All 13 archivist tests pass; all 16 presence tests pass. Committed 205aed4.

**Skipped**: Nothing — Goal 1 Phase 3 is complete.

**Next**: Nag Ladder Tier 2 message content (kingdonb/mecris#139) — decide on coaching copy for escalated walk/Beeminder alerts.

## 🏛️ 2026-04-02 — Session 12: Nag Ladder Tier 2 — escalated coaching copy (complete)

**Planned**: Implement actual Tier 2 coaching copy in `services/reminder_service.py` to replace generic `fallback_message`. (yebyen/mecris#65)

**Done**:
- Orient: NEXT_SESSION.md flagged Nag Ladder Tier 2 as HIGHEST PRIORITY. Confirmed kingdonb/mecris#163 (PR-Test Fix) is now MERGED — blocker resolved.
- Opened plan yebyen/mecris#65; posted analysis comment confirming root cause before coding.
- Read `services/reminder_service.py` and `tests/test_reminder_service.py` in full. Root cause: `_apply_tier2_escalation` sets `tier=2` and `use_template=False` but leaves `fallback_message` as the Tier 1 coaching copy.
- Red: added 3 failing tests — walk_reminder Tier 2 content, beeminder_emergency Tier 2 content, generic type fallback.
- Green: added `_build_tier2_message()` to `ReminderService`; wired into `_apply_tier2_escalation`. Walk path references Boris & Fiona + hours idle; beeminder path names specific goal title + hours idle; generic path is appropriately urgent.
- All 28 tests pass (25 existing + 3 new). Committed 0898f44.

**Skipped**: Arabic review reminder Tier 2 path — the `arabic_review_reminder` goes through `_apply_tier2_escalation` but gets the generic fallback (no `variables` dict). Scope decision deferred to next session.

**Next**: Decide whether `arabic_review_reminder` Tier 2 needs its own `_build_tier2_message` branch (references Arabic goal context); add test if so.

## 🏛️ 2026-04-02 — Session 13: Nag Ladder — Arabic review reminder Tier 2 contextual copy (complete)

**Planned**: Add `arabic_review_reminder` branch in `_build_tier2_message()` with test coverage for idle-based Tier 2 promotion. (yebyen/mecris#66)

**Done**:
- Orient: NEXT_SESSION.md flagged Arabic review reminder Tier 2 path as next pending item. Repos in sync.
- Opened plan yebyen/mecris#66; posted analysis discovering that `arabic_review_reminder` does have `variables` dict — NEXT_SESSION.md note was inaccurate.
- Added `if msg_type == "arabic_review_reminder":` branch to `_build_tier2_message()`: returns "Arabic reviews still overdue after Nh. reviewstack won't fix itself — open Clozemaster NOW."
- Added `test_arabic_review_reminder_tier2_fallback_is_contextual`: reviewstack CRITICAL + arabic_review_reminder sent 7h ago → tier=2, use_template=False, fallback references Arabic context.
- All 29 tests pass. Committed 2b18381.

**Skipped**: Nothing — plan complete.

**Next**: Ghost archivist live validation (requires live environment); upstream PR to kingdonb/mecris for sessions 9-13.
