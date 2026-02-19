# CDD: Intelligent Context-Aware Reminders & Coaching

## 1. Context
The original reminder system was a static cron job that sent SMS notifications based solely on time of day. This led to "nag fatigue" and irrelevant notifications (e.g., reminding to walk during a storm or after a walk was already completed).

## 2. Decision
We decided to transform the system into an **Intelligent Coaching Agent** with two distinct components:

### A. The Execution Layer (Rust/WASM)
- **Role**: Lightweight, fast execution on Fermyon Spin.
- **Responsibility**: Checks immediate environmental constraints (Weather, Daylight) and executes the SMS delivery.
- **Logic**: 
  - IF `weather` is unsafe -> SKIP.
  - IF `walked` is true -> PIVOT message.
  - IF `walked` is false -> REMIND message.

### B. The Reasoning Layer (Python MCP)
- **Role**: Central intelligence with access to full user context.
- **Responsibility**: Synthesizes a "Coaching Insight" based on multiple data streams.
- **Logic**:
  - Aggregates `Beeminder` (Goals), `Obsidian` (Notes), and `Budget` status.
  - Generates a specific "Pivot" recommendation (e.g., "Since you walked, work on Mecris").

## 3. Architecture Refactor
To support this, we refactored the Python server to use a **Service-Repository Pattern**:
- **`CoachingService`**: Pure business logic class.
- **Dependency Injection**: Data sources (Narrator Context, Goal Providers) are injected, enabling robust unit testing without server mocks.

## 4. Test Plan & Verification Strategy

### Level 1: Unit Testing (Logic Verification)
*   **Python**: `tests/test_coaching_service.py`
    *   **Scope**: Verifies `CoachingService` heuristics (High Momentum vs. Low Momentum).
    *   **Technique**: Pure mock injection (no `unittest.patch`).
*   **Rust**: `boris-fiona-walker/src/*.rs`
    *   **Scope**: Verifies `weather.rs` (safe conditions), `daylight.rs` (sunset logic), and message generation.

### Level 2: Integration Testing (Wiring Verification)
*   **Python**: `tests/test_coaching.py`
    *   **Scope**: Verifies the `mcp_server.py` tool correctly instantiates and uses the `CoachingService`.
    *   **Technique**: Mocking the global context providers to simulate server state.

### Level 3: End-to-End Testing (System Verification)
*   **Rust**: `boris-fiona-walker/tests/e2e_tests.rs`
    *   **Scope**: Simulates the full Spin HTTP request/response cycle.
    *   **Status**: Framework established for mocking outbound HTTP calls to OpenWeather/Twilio.

## 5. Deployment Configuration
*   **WASM**: Configured via `spin.toml` with `latitude`/`longitude` variables (defaulting to South Bend, IN).
*   **Secrets**: Requires `openweather_api_key` and `beeminder_api_key` in the runtime environment.
