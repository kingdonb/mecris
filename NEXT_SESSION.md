# Next Session: Narrator integration for semantic bookmark search, or next bot-actionable task

## Current Status (2026-04-25, post-session #51)
- **Semantic bookmark search COMPLETE**: `services/semantic_index.py` implements `BookmarkIndex` (TF-IDF cosine similarity) and `search_bookmarks`. Wired into `mcp_server.py` as `@mcp.tool`. 32 unit tests in `tests/test_semantic_index.py`, all passing. Committed `5be5a79`. Toward kingdonb/mecris#208.
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately (human-required). Blocks PR for Chrome Bookmarks, CopilotLoopback, and Spin SDK v4 migration.
- **yebyen/mecris up to date with kingdonb/mecris**: Both at `71ae7da` before this session's commit `5be5a79`.
- **CopilotLoopback COMPLETE (session #49)**: `ghost/copilot_loopback.py` with `suggest()` and `explain()`. 21 tests. Committed `139d67f`. Toward kingdonb/mecris#206. PR blocked by expired PAT.
- **Spin SDK v4 migration on yebyen/mecris only**: `e6a0bb4` not yet PRed to kingdonb/mecris. Blocked by expired PAT.

## Verified This Session
- [x] **Semantic bookmark search (session #51)**: `services/semantic_index.py` + `tests/test_semantic_index.py` committed `5be5a79`. `PYTHONPATH=. python3 -m pytest tests/test_semantic_index.py -v` → 32 passed, 0 failures. **COMPLETE** — toward kingdonb/mecris#208.
- [x] **search_bookmarks MCP tool**: Wired in `mcp_server.py` with `@mcp.tool(description=...)`. Import from `services.semantic_index`. Returns `{query, total_bookmarks, match_count, matches, source}` with per-match `score` field.
- [x] **yebyen/mecris#280 closed**: Plan issue closed with completion comment.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for `5be5a79` (Semantic Search), `0a29cc7` (Chrome Bookmarks), `139d67f` (CopilotLoopback), and `e6a0nb4` (Spin SDK v4) — all blocked by expired PAT. Closes kingdonb/mecris#208 (partial — Narrator integration deferred), #201 (Chrome), #206 (CopilotLoopback), and #213 (Spin SDK v4).
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Determine if we should maintain a "Legacy Cloud" branch or implement a compatibility shim until the cloud catch-up is complete.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Narrator integration for semantic_index (kingdonb/mecris#208 phase 2)**: Auto-run `search_bookmarks` using current active goal titles as queries, and surface results in `get_narrator_context` response. This is the deferred second half of #208.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **AI Framework Evaluation (Issue #205)**: Matrix doc and POC script committed (`1a459aa`). Remaining: run `scripts/evaluate_aider.py` in an environment with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md` evidence log. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (Issue #214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.

## Infrastructure Notes (carried forward)
- **TF-IDF index is in-memory only**: `BookmarkIndex` re-builds on each `search_bookmarks` call. Acceptable for small bookmark files; if performance becomes an issue, add caching to `mcp_server.py` module level.
- **No new dependencies added**: `services/semantic_index.py` uses only stdlib + no imports from numpy/scipy. Pure Python TF-IDF.
- **Chrome Bookmarks default paths**: macOS: `~/Library/Application Support/Google/Chrome/Default/Bookmarks`; Linux: `~/.config/google-chrome/Default/Bookmarks` or `~/.config/chromium/Default/Bookmarks`.
- **get_bookmarks_by_topic behavior**: Returns `{"source": "not found"}` gracefully when the file doesn't exist (e.g., CI, non-Chrome environments). Safe to call anywhere.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **CopilotLoopback command**: `["gh", "copilot", "--", "-p", full_prompt]` — `--` prevents `gh` from consuming `-p`; passes prompt as arg not stdin. `GH_COPILOT_BASE = ["gh", "copilot", "--"]`.
- **CopilotLoopback default timeout**: 120s (vs HeadlessLoopback's 1800s for gemini). Import from `ghost.copilot_loopback`.
- **Universal Clean Build Strategy**: `find . -name '.venv*' -type d -exec rm -rf {} + && find . -name '__pycache__' -type d -exec rm -rf {} + && uv venv .venv_build --clear --python 3.13 && . .venv_build/bin/activate && uv pip install componentize-py==0.23.0 spin-sdk==4.0.0 && componentize-py -w spin:up/http-trigger@4.0.0 componentize -p . -p .venv_build/lib/python3.13/site-packages app -o component.wasm`
- **SDK v4 async mandate**: `variables.get`, `kv.open_default`, `store.get`, `postgres.query`, and `http.send` are all **async** in SDK 4.0.0.
- **Observant Presence logic**: `is_human_present` checks `/tmp/mecris_presence.lock` and `pgrep -f cli.main`. Logs but does not block registration in `MecrisScheduler`.
- **HCAT sandbox image**: `docker/hcat.Dockerfile` updated with `python3-modules` for stdlib completeness.
- **calculateGoalMet**: `goalMetFromServer || (targetFlowRate != null && targetFlowRate <= 0.0)`. Used in `ReviewPumpWidget`.
- **PLAY MODE threshold**: `outstandingDebt > targetFlowRate * 7` — more than one week of daily work remaining.
- **BECKON threshold**: `outstandingDebt >= 300` — signals user should consider a new Beeminder reviewstack goal.
- **outstanding_debt in LanguageStatDto**: Field added as `Int?` with default `null`. Falls back to `stat.current` when absent. Backend `/languages` API does NOT yet return this field.
- **log-message-py component API**: `POST /internal/log-message` with `{"type": str, "channel": str, "sent_at": ISO|optional}`.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
