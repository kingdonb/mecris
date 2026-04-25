# Next Session: PR Spin SDK v4 migration to kingdonb/mecris (GITHUB_CLASSIC_PAT expired — human-required)

## Current Status (2026-04-25, post-session #47)
- **Majesty Cake Momentum Visualizer COMPLETE (pre-session #47)**: `MomentumOrbState` enum and `momentumOrbState()` function implemented in `MainActivity.kt` (commit `96a3fb5`), full `MomentumVisualizer` composable (pulsing orb + Majesty Rings) wired in at `MainActivity.kt:838`. All 9 `MomentumVisualizerTest` tests pass as part of the 63-test baseline. kingdonb/mecris#195 is **DONE**.
- **Spin SDK v4 migration on yebyen/mecris only**: `e6a0bb4` (Spin SDK v4 migration, Observant Presence, log-message-py) is on yebyen/mecris main but has NOT been PRed to kingdonb/mecris. `tests/test_presence_scheduler.py` — 16 passed. PR creation is **blocked** — `GITHUB_CLASSIC_PAT` returns 401 (expired). yebyen/mecris#276 open, awaiting human action.
- **calculateGoalMet extraction COMPLETE (session #46)**: `calculateGoalMet(goalMetFromServer, targetFlowRate)` in `ReviewPumpCalculator`. 63 total Android tests, `failures="0"`. PR kingdonb/mecris#246 merged at `811936f`.
- **Phase 3 Behavioral Nudge COMPLETE (session #45)**: `calculateIsPlayMode` and `calculateBeckonSignal` in `ReviewPumpCalculator`. `ReviewPumpWidget` surfaces PLAY MODE badge and BECKON pill. All merged via PR #246.

## Verified This Session
- [x] **kingdonb/mecris#195 (Majesty Cake)**: `MomentumOrbState` + `momentumOrbState()` already in `MainActivity.kt:1516`. `MomentumVisualizerTest.kt` — 9 tests already passing in the 63 baseline. `MomentumVisualizer` composable wired at `MainActivity.kt:838` with `aggregateStatus?.all_clear`. **COMPLETE** — no new work needed.
- [x] **Android testDebugUnitTest baseline**: 63 tests, 0 failures, all passing.
- [x] **tests/test_presence_scheduler.py**: 16 passed — Spin SDK v4 migration code is clean.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris without it. Renew the PAT in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main for `e6a0bb4`** (Spin SDK v4 migration) — bot was blocked by expired PAT. Closes yebyen/mecris#276 and kingdonb/mecris#213. Tests green. Body: see yebyen/mecris#276 for details.
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
- [ ] **Verify GOAL MET badge renders on device**: Deploy APK with `a1d3f97`; confirm green "GOAL MET" badge appears in the pressure gauge when goal is satisfied for a language.

### 🤖 Bot-actionable (can be resolved in future sessions)
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
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **calculateGoalMet**: `goalMetFromServer || (targetFlowRate != null && targetFlowRate <= 0.0)`. Used in `ReviewPumpWidget` to render GOAL MET badge and control flow fill bar color.
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
