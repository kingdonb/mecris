# Next Session: Dual-Widget "Debt vs. Flow" UI (kingdonb/mecris#160)

## Current Status (2026-04-24, post-session #39)
- **HCAT Sandbox Dockerfile COMPLETE (session #39)**: `docker/hcat.Dockerfile` created with Alpine 3.21 pinned at `@sha256:48b0309ca019d89d40f670aa1bc06e426dc0931948452e8491e3d65087abc07d`. Non-root `mecris` user. Installs python3 3.12.13, git 2.47.3, uv 0.11.7. Smoke-tested at build time. `scripts/build_hcat.sh` builds and verifies the image. Committed `9ef6800`.
- **Deployment COMPLETE (beta.3)**: Android app and Spin apps (Fermyon & Akamai) fully deployed at `beta.3` tag. Synchronizes backend WASM logic with front-end indicators.
- **budget-governor-py wired into spin.toml (Phase 1.7.2 COMPLETE)**: `mecris-go-spin/sync-service/spin.toml` has `[[trigger.http]]` for `/internal/budget-governor-py`, `[component.budget-governor-py]` with `key_value_stores = ["default"]`. 61/61 pytest tests green. Committed `01783da`.
- **review-pump-py wired into spin.toml (Phase 1.7.1 COMPLETE)**: `mecris-go-spin/sync-service/spin.toml` has `[[trigger.http]]` for `/internal/review-pump-status-py` + `[component.review-pump-py]`. Committed `c3a03bc` + `fa446bb`.
- **BudgetGovernor Python-native WASM POC COMPLETE**: `poc/wasm/budget-governor-py/` — 61/61 tests green. `IncomingHandler` with 5 actions (status, check, record, recommend, gate). Spin KV for persistence; Spin variables for limits; `spin_sdk` outbound HTTP for Helix balance. Committed `4fd02ab`.
- **ReviewPump Python-native WASM POC COMPLETE**: `poc/wasm/review-pump-py/` — 34 tests, parity with Rust review-pump. `LOGIC_VACUUMING_CANDIDATES.md` updated (Phase 1.7).
- **ask_mecris RAG pipeline COMPLETE**: BM25 retrieval + LLM generation (claude-haiku-4-5-20251001). 39 tests pass.
- **The WASM componentize-py pattern is fully established**: both ReviewPump and BudgetGovernor are in `spin.toml`. Next logical work: HCAT Sandbox Dockerfile (#210) or one of the larger backlog items.

## Verified This Session
- [x] **HCAT Sandbox Dockerfile (yebyen/mecris#265)**: `docker/hcat.Dockerfile` built successfully. `docker run --rm --network=none mecris-hcat:test bash -c "whoami"` → `mecris` (non-root). All tools (python3, git, uv) confirmed present. Committed `9ef6800`.
- [x] **Full Deployment (beta.3)**: `make deploy-all` executed successfully. Android client and cloud sync service (Fermyon/Akamai) are at parity.
- [x] **budget-governor-py wired into spin.toml (yebyen/mecris#264)**: `mecris-go-spin/sync-service/spin.toml` — `[[trigger.http]]` at `/internal/budget-governor-py`, `[component.budget-governor-py]` stanza with `key_value_stores = ["default"]`. TOML validated syntactically. 61/61 pytest green. Committed `01783da`.
- [x] **Android test count investigation**: Fixed `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) by injecting `AuthorizationService` to avoid Android framework static initialization.
- [x] **Renovate app install**: Confirmed installed. Renovate bot has created the Dependency Dashboard issue (#218) and is scheduling updates.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- [ ] **Verify poc/wasm/review-pump-py/ builds**: Run `pip install -r requirements.txt && spin py2wasm app -o review-pump-py.wasm` in a `spin`-enabled environment.
- [ ] **Verify poc/wasm/budget-governor-py/ builds**: Run `pip install -r requirements.txt && spin py2wasm app -o budget-governor-py.wasm` in a `spin`-enabled environment.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Dual-Widget "Debt vs. Flow" UI (kingdonb/mecris#160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow. Consumes `goal_met`, `target_flow_rate`, `outstanding_debt` fields already in Python/Rust APIs.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run POC tests.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot`.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks.
- [ ] **Human Yield Presence Detection (Issue #211)**: Add logic to detect human workstation activity and manage the `presence.lock` safely.
- [ ] **Observability: Log Local Notifications (Issue #213)**: Implement remote logging for local Android notifications.
- [ ] **Budget Governor: WASM Port (Issue #214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config (helix_api_url, budget limits) — human-required for deployment.

## Infrastructure Notes (carried forward)
- **HCAT sandbox image**: `docker/hcat.Dockerfile` — Alpine 3.21 `@sha256:48b0309...`, non-root user `mecris`, python3/git/uv installed. Build: `bash scripts/build_hcat.sh`. Runtime: `docker run --network=mecris-egress-only --user=mecris --read-only --tmpfs /tmp mecris-hcat:latest bash -c '<cmd>'`. LAN isolation is runtime-enforced, not Dockerfile-enforced.
- **To refresh Alpine digest**: `docker pull alpine:3.21 && docker inspect --format='{{index .RepoDigests 0}}' alpine:3.21`
- **spin.toml component pattern**: Use `workdir = "../../poc/wasm/<component>/"` for Python WASM components. Build command: `python3 -m pip install --user --break-system-packages -r requirements.txt && spin py2wasm app -o <component>.wasm`. See `arabic-skip-counter`, `review-pump-py`, and `budget-governor-py` in `mecris-go-spin/sync-service/spin.toml`.
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **componentize-py class naming**: Function-export world → `class WitWorld`. HTTP trigger world → `class IncomingHandler(spin_sdk.http.IncomingHandler)`. See `LOGIC_VACUUMING_CANDIDATES.md` for full details.
- **BudgetGovernor WASM action API**: POST `/internal/budget-governor-py` with `{"action": "status"|"check"|"record"|"recommend"|"gate", "bucket": str, "cost": float}`.
- **ask_mecris corpus**: `_rag_retriever` is module-level in `mcp_server.py`. Corpus loaded lazily on first `ask_mecris` call. Force re-index: `_rag_retriever.reset()`. Covers docs/ (95 files) + attic/session-chunks/ (17 files) = 112 documents.
- **ask_mecris result shape**: `{query, result_count, answer, results, note}`. `answer` is `Optional[str]` — prose when `ANTHROPIC_API_KEY` is set and API succeeds, `None` otherwise.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default. Override via `model=` kwarg if needed.
- **smart_nag integration complete**: `ReminderService` receives `walk_history_provider=get_walk_history` (mcp_server.py). SQL: `SELECT start_time FROM walk_inferences WHERE user_id = %s AND start_time >= %s ORDER BY start_time ASC` (last 30 days).
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00; Sovereign Fallback 08:00–20:00; GREEK 17:00–22:30.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning. Safe to import without a live DB.
- **Post-Mortem Generator**: `PostMortemGenerator` in `ghost/post_mortem.py` — fail-open, returns None without NEON_DB_URL.
- **mecris pulse**: `render_pulse(context)` is a pure function — safe to call with any dict. `run_pulse(user_id)` is the async entrypoint importing `get_narrator_context` at call time.
