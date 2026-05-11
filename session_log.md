# Mecris Session Log

*(Archived logs are in `attic/session-chunks/`)*

## 2026-05-11 — 🏛️ test(cli): 10 unit tests for run_presence() CLI handler (session #102)

**Planned**: Add mock-based unit tests for `run_presence()` in `cli/main.py` covering all three actions (`check`, `take`, `release`) and `--local` flag (yebyen/mecris#338).

**Done**: Oriented, confirmed all 54 prior presence tests pass, identified `run_presence()` as having zero unit test coverage. Wrote `tests/test_cli_presence.py` with 10 tests (4 check variants, 2 take, 2 release, 2 local-flag routing). All 64 presence tests pass. Commit `cff57dd`. Closes yebyen/mecris#338.

**Skipped**: Nothing — scope was correctly sized and completed in one session.

**Next**: No remaining bot-actionable presence work. Next session should look for open bugs, new issues on kingdonb/mecris, or begin `AI Framework Evaluation (kingdonb/mecris#205)` (requires Aider + LLM key — may be human-actionable only).

## 2026-05-10 — 🏛️ fix(tests): add psycopg2 bootstrap to test_presence_neon (session #100)

**Planned**: Implement `bin/mecris presence` command with lock file mechanism and unit tests (yebyen/mecris#336).

**Done**: Discovered `ghost/presence.py`, `cli/main.py presence` subcommand, and scheduler integration were already complete. Found 13 failing tests in `tests/test_presence_neon.py` — `ghost.presence` sets `psycopg2=None` at module level when not installed, causing `patch("ghost.presence.psycopg2.connect", ...)` to raise `AttributeError`. Added `sys.modules.setdefault("psycopg2", _mock_psycopg2)` bootstrap and in-place patch of `ghost.presence.psycopg2` and `._PSYCOPG2_AVAILABLE`. 54 presence tests now pass (was 41). Commit `83f6b0a`.

**Skipped**: Nothing — scope was correctly sized.

**Next**: Observability Mandate Bus Standardization (kingdonb/mecris#245) — verify JSON response format matches Standard Bus spec in `docs/OBSERVABILITY_MANDATE.md`.

## 2026-05-10 — 🏛️ feat(obs): mirror _write_obs_status to in-memory attrs; surface in system_pulse

**Planned**: Add `last_status`, `intent`, `last_error` as in-memory attributes to `MecrisScheduler`; mirror each Neon write in `_write_obs_status()`; surface in `get_narrator_context` `system_pulse`. Plan: yebyen/mecris#335.

**Done**: Added 3 in-memory attrs to `MecrisScheduler.__init__`; `_write_obs_status()` now updates them on success. `get_narrator_context` `system_pulse` includes all three fields. 6 new tests in `TestWriteObsStatusInMemoryMirror` — all 13 in `test_scheduler_election.py` pass in 0.69s. Commit `1c78824`. Closes yebyen/mecris#335.

**Skipped**: Nothing — plan was fully executed.

**Next**: Remaining Observability Mandate #245 subtasks: Rust WASM backend (`sync-service/src/lib.rs`) to record Silent Decisions, and Android `HeartbeatWorker` obs fields — both require non-Python work. Next bot-actionable frontier: kingdonb/mecris#211 (Human Yield / Presence Detection) unit tests.

## 2026-05-10 — fix(tests): psycopg2 bootstrap in test_system_health + test_health_checker

**Planned**: Add `sys.modules["psycopg2"] = MagicMock()` module-level bootstrap to `tests/test_system_health.py` and `tests/test_health_checker.py` so all 16 failing tests pass without psycopg2 installed in CI. Plan: yebyen/mecris#334.

**Done**: Added 4-line bootstrap block (import sys, MagicMock, setdefault) to both test files. `PYTHONPATH=. python3 -m pytest tests/test_system_health.py tests/test_health_checker.py -v` → 19 passed, 0 failed. Commit `5e9df24`. Closes yebyen/mecris#334.

**Skipped**: Nothing — scope was small and exactly matched the plan.

**Next**: Explore kingdonb/mecris#245 (Observability Mandate) subtasks or kingdonb/mecris#211 (Human Yield / Presence Detection) for next bot-actionable unit of work.

## 2026-05-10 — 🏛️ test(whatsapp): 11 unit tests for WhatsAppTemplateManager

**Planned**: Enhance obsidian_client.py todo parser for alternate checkbox styles (kingdonb/mecris#196) — pivoted after discovering work was already done in session #16 (commit `ebe3d30`). Pivoted to coverage gap hunt, landed on `WhatsAppTemplateManager`.

**Done**: Wrote `tests/test_whatsapp_template_manager.py` — 11 unit tests covering `fetch_all_statuses()` (dict approval, list approval, empty/None approval, Twilio exception), `get_approved_pool()` (approved filter, empty result, error path), and `sync_approved_templates()` (JSON write, count, last_updated field). Bootstrap: mock `twilio` + `dotenv` in `sys.modules` before import; `__new__` bypass for constructor. All 11 pass in 0.11s. Commit `9126bbf`. Closes yebyen/mecris#333.

**Skipped**: Nothing — full completion.

**Next**: Continue Empty Backlog Protocol — hunt for more coverage gaps or explore kingdonb/mecris epics (#245, #211, #208) for bot-actionable subtasks.

## 2026-05-10 — Bus Standardization: expose obs fields in fetch_system_pulse modalities

**Planned**: Update `fetch_system_pulse()` in `mcp_server.py` to SELECT `last_status`, `intent`, `last_error` from `scheduler_election` alongside existing fields; add unit tests asserting these fields appear (null-safe for pre-migration DBs). Plan: yebyen/mecris#337.

**Done**: Updated SQL in `fetch_system_pulse()` to SELECT 6 columns (role, heartbeat, minutes_since, last_status, intent, last_error) with graceful fallback to a NULL-only query when migration v8 columns are absent. Each modality dict now includes `last_status`, `intent`, `last_error` keys. Wrote `tests/test_system_pulse.py` with 6 tests: obs fields present, obs fields NULL (pre-migration), empty result, unknown_cloud skipped, display name mapping, no-NEON_DB_URL early return. All 6 pass; 19 existing mcp_server/daily_aggregate tests unaffected. Commit `a410df8`. Closes yebyen/mecris#337.

**Skipped**: Nothing — full completion.

**Next**: Human Yield `bin/mecris presence` CLI (kingdonb/mecris#211) or apply migration v8 to production Neon to activate obs fields end-to-end.
