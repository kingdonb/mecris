# Next Session: Backport "REMAINING TODAY" counter or Majesty Cake to Android (kingdonb/mecris#194 / #195)

## Current Status (2026-04-24, post-session #45)
- **Phase 3 Behavioral Nudge COMPLETE (session #45)**: `calculateIsPlayMode` (debt > 7× daily flow target → amber "PLAY MODE" badge) and `calculateBeckonSignal` (debt ≥ 300 → purple "BECKON ✦" pill) added to `ReviewPumpCalculator`. `ReviewPumpWidget` surfaces both. 7 new tests; 21 in `ReviewPumpCalculatorTest`, 57 total — all passing. Committed `d7d86eb`. Plan yebyen/mecris#273 closed. PR: kingdonb/mecris#246.
- **Flow fill bar COMPLETE (session #44)**: Phase 2 of kingdonb/mecris#160 delivered. `calculateFlowFillRatio` — capped at 1.0. Amber/green fill Box in pressure gauge track. Committed `bfc77b4`.
- **Debt-coverage ratio indicator COMPLETE (session #43)**: Phase 1 of kingdonb/mecris#160 delivered. `outstanding_debt: Int?` in `LanguageStatDto`. Thin bottom-edge line amber/green. Committed `cdaa79c`.
- **Android NagNotificationManager HTTP logging COMPLETE (session #42)**: Fire-and-forget POST to `/internal/log-message` after each `notify()`. Committed `ed6692b`.
- **log-message-py WASM endpoint COMPLETE (session #41)**: `poc/wasm/log-message-py/app.py` — 40/40 pytest tests. Committed `5addf51`.

## Verified This Session
- [x] **Phase 3 Behavioral Nudge (yebyen/mecris#273 / kingdonb/mecris#160 Phase 3)**: `calculateIsPlayMode` and `calculateBeckonSignal` green (7 new tests). `ReviewPumpWidget` shows PLAY MODE badge and BECKON pill. `testDebugUnitTest` exits 0 (57 total). Committed `d7d86eb`. PR kingdonb/mecris#246.

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
- [ ] **Verify debt-coverage line renders on device**: Deploy updated APK; confirm amber/green bottom-edge line appears in each language gauge.
- [ ] **Verify flow fill bar renders on device**: Deploy APK with `bfc77b4`; confirm amber fill bar appears proportionally, turning green when `goal_met` is true.
- [ ] **Verify PLAY MODE / BECKON render on device**: Deploy APK with `d7d86eb`; confirm amber "PLAY MODE" badge for Arabic (large backlog) and purple "BECKON ✦" pill when `outstanding_debt >= 300`. Confirm Greek does NOT show PLAY MODE when debt is small.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Backport "REMAINING TODAY" counter (kingdonb/mecris#194)**: `LanguageStatDto` already has `target_flow_rate`, `absolute_target`, `goal_met`. Display "REMAINING TODAY" with server-normalized `target_flow_rate`; show "GOAL SATISFIED" badge when `target_flow_rate <= 0` or `goal_met`. Mostly additive UI work on existing widget.
- [ ] **Backport "Majesty Cake" Momentum Visualizer (kingdonb/mecris#195)**: Pulsing orb with "Majesty Rings" when `all_clear` is true (all languages `goal_met`). Reference: `web/src/components/MomentumVisualizer.tsx`. Requires new Compose component + `AggregateStatusResponseDto` data.
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
- **PLAY MODE threshold**: `outstandingDebt > targetFlowRate * 7` — more than one week of daily work remaining. Arabic (2600 debt, ~100/day) will almost always show PLAY MODE. Greek clears quickly, typically will not.
- **BECKON threshold**: `outstandingDebt >= 300` — signals user should consider a new Beeminder reviewstack goal.
- **Flow fill bar in ReviewPumpWidget**: `flowFillRatio = calculateFlowFillRatio(stat.daily_completions, remainingToday.toInt())`. Fill Box amber when not `goalMet`, green when `goalMet`. Between background track Box and Canvas.
- **outstanding_debt in LanguageStatDto**: Field added as `Int?` with default `null`. Falls back to `stat.current` when absent. Backend `/languages` API does NOT yet return this field.
- **calculateDebtCoverageRatio**: Returns 0.0f when `outstandingDebt <= 0`. Returns raw ratio (can exceed 1.0). UI clamps to 1.0 for line width.
- **calculateFlowFillRatio**: Returns 0.0f when `targetFlowRate <= 0`. Capped at 1.0.
- **calculateIsPlayMode**: Returns false when `targetFlowRate <= 0`. True when `outstandingDebt > targetFlowRate * 7`.
- **calculateBeckonSignal**: True when `outstandingDebt >= 300`.
- **log-message-py component API**: `POST /internal/log-message` with `{"type": str, "channel": str, "sent_at": ISO|optional}`. Returns `{"logged": true, "entry_count": int, "logged_at": ISO}`. `GET` returns `{"entries": [...], "entry_count": int}`. Spin KV key: `"message_log"`, rolling cap 1000 entries.
- **NagNotificationManager API**: `showNag(title, message, packageToLaunch?, type?)`. Accepts optional `SyncServiceApi` for audit logging. If `api` is null, notification fires silently.
- **spin.toml component pattern**: Use `workdir = "../../poc/wasm/<component>/"` for Python WASM components.
- **Human Yield Presence**: `ghost/presence.py` — `is_human_present(lock_path=None, ttl=PRESENCE_TTL_SECONDS)` checks `SYSTEM_LOCK_PATH` (`/tmp/mecris_presence.lock`) first, then `pgrep -f cli.main`.
- **HCAT sandbox image**: `docker/hcat.Dockerfile` — Alpine 3.21 `@sha256:48b0309...`, non-root user `mecris`.
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **BudgetGovernor WASM action API**: POST `/internal/budget-governor-py` with `{"action": "status"|"check"|"record"|"recommend"|"gate", "bucket": str, "cost": float}`.
- **ask_mecris corpus**: `_rag_retriever` is module-level in `mcp_server.py`. Corpus loaded lazily. Covers docs/ (95 files) + attic/session-chunks/ (17 files) = 112 documents.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00; Sovereign Fallback 08:00–20:00; GREEK 17:00–22:30.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
