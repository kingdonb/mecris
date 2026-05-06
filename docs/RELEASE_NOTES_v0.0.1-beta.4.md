# Release Notes: v0.0.1-beta.4

**Date**: May 2, 2026

## Overview
This release represents a massive operational maturity upgrade for the Mecris accountability system. It introduces the foundational architectural plans to prevent unmetered agent autonomy (the API Proxy), massive expansions in test coverage, significant component stability, and major upgrades to the underlying Spin WASM SDK. 

## 🚨 Security & Accountability
- **API Proxy Budget Defense Plan**: Following a critical autonomous spend incident, we've finalized the architectural plan to introduce an Internal API Intercept proxy. This will hard-enforce token limits and budget checks against the Neon DB before any LLM request leaves our infrastructure.
- **Runaway Spend Protections**: Disabled the unmetered `mecris-bot` cron triggers and revoked overly-permissive `/tdg` skill access. The `pr-test` workflow test output has also been silenced to drastically reduce CI context bloat.
- **JIT Secret Manager**: Implemented secure JIT secret resolution with a robust fallback to a Neon DB `secure_variables` table if environmental keys are missing.

## 🧪 Testing & Reliability
- **Test Coverage Explosion**: Our agent-driven Test-Driven Generation (TDG) loop successfully blanketed the Python codebase with over **800+ new unit tests**, moving coverage near 100% across critical infrastructure scripts, CLI tools, and WASM components.
- **WASM Test Skew Resolved**: Eradicated the test-implementation mismatch in `budget-governor-py` and `arabic-skip-counter`. Python pure-logic components now fully align with the WASM `spin-sdk` HTTP triggers and run reliably in headless test environments.
- **CI Improvements**: Silenced Git submodule recursion errors, migrated GitHub Actions to Node 24, and pinned action SHAs for reproducible security.

## 🧠 Cognitive Features
- **Semantic Bookmarks & RAG**: Merged `chunk_session_logs.py` and built a pure-Python TF-IDF Semantic Bookmark index. The `get_narrator_context` MCP tool now intelligently injects the user's most relevant Chrome bookmarks based on their at-risk Beeminder goals.
- **Notification Preferences**: Fully shipped the write-path (`POST /profile`) allowing granular control of `step_threshold`, `window_start_hour`, and `rate_limit_minutes` in the Rust reminder backend.

## 🏗️ Architecture & SDK
- **Spin SDK 4.0.0**: Upgraded all Rust and Python WASM components to the newest Spin SDK 4.0.0 specification.
- **Dual-Track ABI Testing**: Documented the "Intentional Failure" strategy in the CI/CD Evolution Plan. The pipeline now explicitly asserts SDK v3 sync API on `legacy-cloud` while tracking SDK v4 async API readiness on `main`. 
- **Build Isolation**: Enforced `$HOME/.local/bin/uv` availability during all `spin build` commands to ensure strictly hermetic Python WASM compilation processes.

*Signed off by mecris-bot & Kingdon*
