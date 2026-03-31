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
