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

## 2026-03-27 — Verify Android sync/multipliers, resolve familiar_id, and draft Pump Calculation fix

**Planned**: Verify Issue #3 manual tests (Android app interaction).
**Done**:
- Verified Android Background/Manual Sync: correct Beeminder datapoints and comments ✅
- Verified Multiplier Lever: 2x Arabic / 5x Greek persisted in Neon ✅
- Fixed Familiar ID: added resolve_user_id to NeonSyncChecker and GroqOdometerTracker ✅
- Reloaded MCP server: get_language_velocity_stats now reflects correct multipliers for 'yebyen' ✅
- Drafted Issue #6: Audit and fix Review Pump's handling of Points vs. Cards units.
**Skipped**: None.
**Next**: Execute Issue #6 (Pump logic audit) to ensure unit consistency for card-based vs. point-based goals.

...

## 2026-03-30 — Arabic Phase 3: escalation ladder for ignored arabic_review_reminder

**Planned**: Add `arabic_review_escalation` reminder type in \`reminder_service.py\` — fires when skip_count >= 3 consecutive ignored cycles, 1h cooldown, distinct message; 2+ new tests; all existing tests still pass (plan yebyen/mecris#42).
**Done**: Implemented exactly as planned. `ReminderService.__init__` gains 5th optional param `skip_count_provider` (async fn → int). When skip_count >= 3 and `arabic_review_escalation` cooldown (1h) elapsed: fires escalation with skip count in var "3", urgency_template_sid. Graceful fallback to base reminder if provider raises. 3 new tests cover: fires after 3 cycles, resets when cards_done (skip_count=0), respects 1h cooldown. All 13 tests pass. Committed as `c769016`.
**Skipped**: MCP wire-up for skip_count_provider (no MCP function returns skip count yet — next session work). Dedicated WhatsApp template for escalation (still uses urgency_alert_v2 — template creation is out-of-band user work).
**Next**: Wire skip_count_provider into mcp_server.py (need get_arabic_skip_count MCP function or derive from language_stats.cards_today + message_log). Check if PR #158 merged by kingdonb; open fresh sync PR if so.

## 2026-03-31 — Wire skip_count_provider into mcp_server.py (Arabic Phase 3 MCP wire-up)

**Planned**: Add `get_arabic_skip_count(user_id)` to `mcp_server.py` and wire it as `skip_count_provider` in `ReminderService` instantiation, so Arabic Phase 3 escalation can fire in production (plan yebyen/mecris#43).
**Done**: Extracted `count_arabic_reminders(neon_url, user_id, hours=24)` into `services/arabic_skip_counter.py` (testable, lazy psycopg2 import). Added `get_arabic_skip_count()` async wrapper in `mcp_server.py` using `asyncio.to_thread`; returns 0 if NEON_DB_URL unset. Updated `ReminderService` instantiation with `skip_count_provider=get_arabic_skip_count`. 4 new tests using `sys.modules` psycopg2 patching. All 17 tests pass. Committed as `6f73b92`.
**Skipped**: Opening sync PR to kingdonb (next session work). Dedicated WhatsApp template for escalation (requires Twilio console — user work).
**Next**: Open sync PR yebyen/mecris → kingdonb/mecris for commit `6f73b92`. Check Arabic reviewstack Beeminder status manually.

## 2026-03-31 — Open sync PR yebyen/mecris → kingdonb/mecris for Arabic Phase 3 MCP wire-up

**Planned**: Open sync PR from yebyen/mecris main to kingdonb/mecris main carrying `6f73b92` (skip_count_provider wire-up) and `97d8734` (archive) (plan yebyen/mecris#44).
**Done**: kingdonb/mecris#159 opened via GITHUB_CLASSIC_PAT (fine-grained token lacks cross-repo PR permission). PR carries 2 commits, state OPEN, awaiting kingdonb review/merge. Plan issue #44 created, commented, and closed.
**Skipped**: Nothing — plan completed in full.
**Next**: Check if kingdonb/mecris#159 has been merged. If so, check upstream sync and pick next work item (WASM POC, Android #122, or Helix balance validation).

## 2026-03-31 — Research componentize-py + Spin compatibility for Python-native WASM

**Planned**: Research `componentize-py` compatibility with Spin runtime and update `LOGIC_VACUUMING_CANDIDATES.md` with a YES/NO/PARTIAL assessment for Python-native WASM migration of services/ modules (plan yebyen/mecris#45).
**Done**: Read existing LOGIC_VACUUMING_CANDIDATES.md + reminder_service.py + arabic_skip_counter.py. Documented componentize-py findings in yebyen/mecris#45 comment (web search unavailable; used training knowledge through Aug 2025). Updated LOGIC_VACUUMING_CANDIDATES.md with Candidate 3 section covering limitations table, per-service assessment (review_pump: YES, arabic_skip_counter: PARTIAL/psycopg2 blocker, reminder_service: PARTIAL/async refactor needed, budget_governor: PARTIAL/I/O layer only), and Phase 1.5 addition to migration sequence. Committed as `b3db3f2`.
**Skipped**: POC implementation (research-only session; implementation is next step). Web search blocked in runner environment — knowledge-based research only.
**Next**: Decide Phase 1 path (componentize-py Python vs Rust) for ReviewPump WASM port; create plan issue and execute. Check if kingdonb/mecris#159 merged.

## 2026-03-31 — Logic Vacuuming Phase 1.5a: arabic_skip_counter psycopg2 → Neon HTTP API

**Planned**: Rewrite `services/arabic_skip_counter.py` to use Neon HTTP API (`/sql` endpoint via httpx) instead of psycopg2; update tests to mock at HTTP layer; add test verifying request shape. (yebyen/mecris#46)

**Done**: Implementation complete. `arabic_skip_counter.py` now derives `https://{host}/sql` from the postgres:// URL, authenticates with Basic auth (base64 user:password), and POSTs `{"query": ..., "params": [...]}`. SQL uses OR conditions instead of `ANY(%s)` to avoid Neon HTTP array serialization issues. All 4 original tests rewritten for httpx mocking; 1 new test (`test_neon_http_request_shape`) verifies URL, auth header, and body shape. Committed as `296a14d`. 18/18 tests pass (13 reminder_service + 5 skip_count).

**Skipped**: Phase 1.5b (componentize-py WASM wrap) — correct scope split; 1.5a was the prerequisite. Phase 1 (ReviewPump WASM port) — not started this session.

**Next**: Phase 1.5b — wrap arabic_skip_counter.py as a componentize-py/spin-python-sdk WASM component. WIT interface: `count-arabic-reminders: func(neon-url: string, user-id: string, hours: u32) -> u32`. Note: httpx outbound HTTP works in WASM via Spin outbound HTTP capability — no further I/O changes needed.

## 2026-03-31 — Post-Mortem: Greek Data Corruption (ellinika)

**Planned**: Investigate reports of "spurious" Greek Beeminder data points for the `ellinika` goal; find the source and provide a fix plan.

**Done**: Root cause identified as a category error: treating the `ellinika` odometer/cumulative goal as a backlog-tracking snapshot. Found duplicated incorrect mapping in `scripts/clozemaster_scraper.py` (Python) and `mecris-go-spin/sync-service/src/lib.rs` (Rust/Failover). Published full post-mortem in `docs/postmortems/2026-03-31-greek-data-corruption.md`. Added `NEXT_SESSION.md` recovery steps and `GEMINI.md` directive #6 (Goal Type Awareness) to prevent recurrence.

**Next**: Bot to execute recovery plan: remove Greek Beeminder push from Python/Rust scrapers; update regression tests; verify with dry-run.
