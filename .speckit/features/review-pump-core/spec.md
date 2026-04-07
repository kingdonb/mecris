# Feature Specification: Zero-Split-Brain Core (The Review Pump)
**Status:** DRAFT
**Date:** 2026-04-07
**Feature ID:** CORE-001 (The Review Pump Math)

## 1. Intent
To fulfill the "Zero-Split-Brain" axiom by encapsulating the core math of the "Review Pump" into a pure, host-agnostic WebAssembly (WASM) component. This component must execute identically across the Kubernetes Operator (Go), the Spin API (Rust), the MCP Server (Python), and the Android App (Kotlin), ensuring a single, undeniable source of truth for all accountability logic.

## 2. The WASM vs. Host Boundary
This specification explicitly delineates the boundary between pure calculation (The Brain) and external reality (The Host).

### 2.1 The Host's Responsibility (I/O & Reality)
The host environments (Go, Python, Kotlin, Rust) are strictly responsible for gathering data and executing side-effects. The host MUST:
*   Fetch the user's current backlog of reviews from the Clozemaster API.
*   Fetch the user's current goal status and daily clearance targets from the Beeminder API.
*   Read the current `pump_multiplier` lever setting from the Neon Database (or K8s CRD).
*   Provide the current UTC timestamp.
*   Send SMS notifications, patch K8s CRDs, or render Android UI elements based on the WASM Brain's output.

### 2.2 The Brain's Responsibility (Pure Calculation)
The WASM Brain is a pure mathematical function. It takes a structured JSON input and returns a structured JSON output. It performs NO network calls and maintains NO internal state.

## 3. Functional Requirements

### FR-001: The Pump Calculation Engine
The Brain must accept a `PumpRequest` JSON object containing:
*   `current_backlog` (Integer): Total pending reviews across all languages.
*   `pump_multiplier` (Float): The intensity lever (e.g., 1.0, 2.0, 4.0, 10.0).
*   `base_daily_target` (Integer): The minimum baseline daily goal (e.g., 100).

It must calculate and return a `PumpResult` JSON object containing:
*   `required_clearance` (Integer): The calculated number of reviews the user must complete today.
*   `is_goal_met` (Boolean): True if the current progress meets or exceeds the `required_clearance`.
*   `pump_status` (String): A human-readable diagnostic status (e.g., "Maintenance", "Aggressive", "Overdrive").

### FR-002: The Multiplier Math
The `required_clearance` must be calculated dynamically based on the backlog and multiplier.
*   If `pump_multiplier == 1.0` (Maintenance): `required_clearance = base_daily_target`. The pump only asks the user to maintain their daily streak, leaving the backlog untouched.
*   If `pump_multiplier > 1.0` (Active Pumping): The engine must calculate a clearance target that aggressively eats into the backlog over time.
    *   *Formula:* `required_clearance = base_daily_target + (current_backlog * (pump_multiplier - 1.0) * 0.10)`. (This formula dictates that a 2.0 multiplier attempts to clear 10% of the backlog daily, 4.0 clears 30%, etc.).

## 4. Edge Cases

### EC-001: Negative or Zero Backlog
If `current_backlog <= 0`, the `required_clearance` must never fall below the `base_daily_target`. The system should gracefully log a "Cavitation" status, indicating the pump is running dry but still requires baseline daily maintenance.

### EC-002: Math Rounding
All fractional clearance targets must be rounded UP (`ceil`) to the nearest whole integer to ensure the backlog is mathematically guaranteed to reach absolute zero.

## 5. Success Criteria

*   **SC-001 (Host Ignorance):** The WASM component compiles to `wasm32-unknown-unknown` (or `wasm32-wasip1`) and imports zero host functions for network or disk access.
*   **SC-002 (Identical Output):** Passing the identical `PumpRequest` JSON string from Python, Go, and Kotlin yields the exact same byte-for-byte `PumpResult` JSON string from the WASM module.
*   **SC-003 (Deterministic State):** Given a backlog of 500, a base target of 100, and a multiplier of 2.0, the WASM component must consistently output a `required_clearance` of 150.
