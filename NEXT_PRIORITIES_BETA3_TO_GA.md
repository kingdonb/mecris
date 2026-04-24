# Roadmap from beta.3 to v0.0.1 (GA)

## Immediate Actions for beta.3 Polish
*   **Fermyon Cloud Variable Configuration (#214)**: Set `helix_api_url` and budget limits in the Fermyon dashboard so `budget-governor-py` functions correctly.
*   **Verify RAG Production Quality**: Confirm `ANTHROPIC_API_KEY` is active in the production MCP server environment for `ask_mecris`.
*   **Android `PocketIdAuthTest` Fix**: Resolve the `ExceptionInInitializerError` at line 35 to ensure a green test suite.

## Epic 1: The Autonomous Engine (The "Ghost")
*   **Human Yield Presence Detection (#211)**: Implement workstation activity detection to manage `presence.lock` safely.
*   **The Archivist Daemon**: Finalize the background service for autonomous goal reconciliation and RAG pipeline execution.

## Epic 2: Hardened Security (HCAT)
*   **HCAT Sandbox Dockerfile (#210)**: Ensure all autonomous turns run in a hardened, SHA-pinned container.
*   **Autonomous Security: JIT Secret Manager (#204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.

## Epic 3: The Complete WASM Brain
*   **Port Twilio to WASM Brain (#167)**: Move SMS/WhatsApp dispatch logic entirely into the `sync-service` Rust module.
*   **Rust Reminder Engine (#169)**: Move heuristics (2000-step threshold, sleep windows, weather checks) into Rust natively.

## Epic 4: Observability & UX
*   **Dual-Widget "Debt vs. Flow" UI (#160)**: Android app visualization of daily "Flow" (Review Pump targets) vs. long-term "Debt" (Beeminder runway).
*   **Log Local Notifications (#213)**: Implement telemetry to verify Android app local alarms are firing.
