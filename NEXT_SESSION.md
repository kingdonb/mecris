# Next Session: Dual-Widget "Debt vs. Flow" UI — Phase 3 (kingdonb/mecris#160)

## Current Status (2026-04-24, post-session #44)
- **Flow fill bar COMPLETE (session #44)**: Phase 2 of kingdonb/mecris#160 delivered. `calculateFlowFillRatio(completedToday, targetFlowRate): Float` added to `ReviewPumpCalculator` — capped at 1.0 for UI bar, returns 0.0 when targetFlowRate ≤ 0. `ReviewPumpWidget` now draws an amber/green fill Box overlaying the pressure gauge track, proportional to `daily_completions / target_flow_rate`; turns solid green when `goal_met` is true. 5 new unit tests; 24 total tests green. Committed `bfc77b4`. Plan yebyen/mecris#271 closed.
- **Debt-coverage ratio indicator COMPLETE (session #43)**: Phase 1 of kingdonb/mecris#160 delivered. `outstanding_debt: Int?` added to `LanguageStatDto` (defaults to `current` if backend omits it). `calculateDebtCoverageRatio(completedToday, outstandingDebt): Float` added to `ReviewPumpCalculator`. Gauge Canvas draws thin bottom-edge line: amber (`0xFFFFB300`) when coverage < 1.0, green (`0xFF00C853`) when cleared. Committed `cdaa79c`.
- **Android NagNotificationManager HTTP logging COMPLETE (session #42)**: `NagNotificationManager.kt` updated — fire-and-forget `GlobalScope.launch(Dispatchers.IO)` POSTs `{type, channel: "android_native", sent_at}` to `/internal/log-message` after each `notify()`. Committed `ed6692b`.
- **log-message-py WASM endpoint COMPLETE (session #41)**: `poc/wasm/log-message-py/app.py` implements `POST /internal/log-message`. 40/40 pytest tests green. Committed `5addf51`.
- **Human Yield Presence Detection COMPLETE (session #40)**: `ghost/presence.py` extended. 16 new tests. Committed `e5100cf`.

## Verified This Session
- [x] **Flow fill bar (yebyen/mecris#271 / kingdonb/mecris#160 Phase 2)**: `calculateFlowFillRatio` — 5 test cases green (no-work, partial, exact, over-achieved, zero-target). Amber/green fill Box added to `ReviewPumpWidget` pressure gauge track. `testDebugUnitTest` exits 0 (24 total). Committed `bfc77b4`.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Verify kingdonb/mecris#213 end-to-end**: Deploy updated APK and confirm audit logs appear in Spin KV via `GET /internal/log-message` after a real notification fires on device.
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- [ ] **Verify poc/wasm/review-pump-py/ builds**: Run `pip install -r requirements.txt && spin py2wasm app -o review-pump-py.wasm` in a `spin`-enabled environment.
- [ ] **Verify poc/wasm/budget-governor-py/ builds**: Same as above.
- [ ] **Verify poc/wasm/log-message-py/ builds**: `cd poc/wasm/log-message-py && pip install -r requirements.txt && spin py2wasm app -o log-message-py.wasm`.
- [ ] **Verify debt-coverage line renders on device**: Deploy updated APK; confirm amber/green bottom-edge line appears in each language gauge based on `daily_completions` vs `outstanding_debt` (or `current` as fallback). Backend may need to add `outstanding_debt` field to `/languages` API response.
- [ ] **Verify flow fill bar renders on device**: Deploy APK with `bfc77b4`; confirm amber fill bar appears proportionally in each gauge, turning green when `goal_met` is true.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Dual-Widget Phase 3 — Behavioral Nudge (kingdonb/mecris#160)**: UI should visually prioritize "Play mode" when debt is high; provide a "Beckon" signal when backlog is large enough to warrant a new `reviewstack` goal.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run POC tests.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot`.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks.
- [ ] **Budget Governor: WASM Port (Issue #214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.

## Infrastructure Notes (carried forward)
- **Flow fill bar in ReviewPumpWidget**: `flowFillRatio = calculateFlowFillRatio(stat.daily_completions, remainingToday.toInt())`. Fill Box uses `fillMaxWidth(fraction = flowFillRatio)`, height 8dp, amber (`0xFFFFB300`) when not `goalMet`, green (`0xFF00C853`) when `goalMet`. Rendered between background track Box and Canvas in the pressure gauge stack.
- **outstanding_debt in LanguageStatDto**: Field added as `Int?` with default `null`. `ReviewPumpWidget` falls back to `stat.current` when absent (`outstandingDebt = stat.outstanding_debt ?: stat.current`). Backend `/languages` API does NOT yet return this field — the fallback means the debt line uses the Beeminder "current" count until the backend is updated.
- **calculateDebtCoverageRatio**: `ReviewPumpCalculator.calculateDebtCoverageRatio(completedToday: Int, outstandingDebt: Int): Float`. Returns `0.0f` when `outstandingDebt <= 0`. Returns raw ratio (can exceed 1.0 for over-cleared). UI clamps to 1.0 for line width.
- **calculateFlowFillRatio**: `ReviewPumpCalculator.calculateFlowFillRatio(completedToday: Int, targetFlowRate: Int): Float`. Returns `0.0f` when `targetFlowRate <= 0`. Capped at 1.0 (over-achievement is full bar). 24 unit tests total in `ReviewPumpCalculatorTest`.
- **log-message-py component API**: `POST /internal/log-message` with `{"type": str, "channel": str, "sent_at": ISO|optional}`. Returns `{"logged": true, "entry_count": int, "logged_at": ISO}`. `GET` returns `{"entries": [...], "entry_count": int}`. Spin KV key: `"message_log"`, rolling cap 1000 entries. Source: `poc/wasm/log-message-py/app.py`.
- **NagNotificationManager API**: `showNag(title, message, packageToLaunch?, type?)`. Accepts optional `SyncServiceApi` for audit logging. If `api` is null, notification fires silently. Type values: `arabic_pressure`, `walk_reminder`, `greek_reminder`, `unknown` (default).
- **spin.toml component pattern**: Use `workdir = "../../poc/wasm/<component>/"` for Python WASM components. Build command: `python3 -m pip install --user --break-system-packages -r requirements.txt && spin py2wasm app -o <component>.wasm`. See `arabic-skip-counter`, `review-pump-py`, `budget-governor-py`, and `log-message-py` in `mecris-go-spin/sync-service/spin.toml`.
- **Human Yield Presence**: `ghost/presence.py` — `is_human_present(lock_path=None, ttl=PRESENCE_TTL_SECONDS)` checks `SYSTEM_LOCK_PATH` (`/tmp/mecris_presence.lock`) first, then `pgrep -f cli.main`. `MecrisScheduler._start_leader_jobs()` calls this before registering jobs.
- **HCAT sandbox image**: `docker/hcat.Dockerfile` — Alpine 3.21 `@sha256:48b0309...`, non-root user `mecris`, python3/git/uv installed. Build: `bash scripts/build_hcat.sh`.
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **componentize-py class naming**: Function-export world → `class WitWorld`. HTTP trigger world → `class IncomingHandler(spin_sdk.http.IncomingHandler)`.
- **BudgetGovernor WASM action API**: POST `/internal/budget-governor-py` with `{"action": "status"|"check"|"record"|"recommend"|"gate", "bucket": str, "cost": float}`.
- **ask_mecris corpus**: `_rag_retriever` is module-level in `mcp_server.py`. Corpus loaded lazily on first `ask_mecris` call. Force re-index: `_rag_retriever.reset()`. Covers docs/ (95 files) + attic/session-chunks/ (17 files) = 112 documents.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default. Override via `model=` kwarg if needed.
- **smart_nag integration complete**: `ReminderService` receives `walk_history_provider=get_walk_history` (mcp_server.py).
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00; Sovereign Fallback 08:00–20:00; GREEK 17:00–22:30.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **Post-Mortem Generator**: `PostMortemGenerator` in `ghost/post_mortem.py` — fail-open, returns None without NEON_DB_URL.
- **mecris pulse**: `render_pulse(context)` is a pure function — safe to call with any dict. `run_pulse(user_id)` is the async entrypoint importing `get_narrator_context` at call time.
