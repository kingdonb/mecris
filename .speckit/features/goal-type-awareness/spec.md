# Feature Specification: Goal Type Awareness (The Safety Valve)
**Status:** DRAFT
**Date:** 2026-04-07
**Feature ID:** CORE-003 (Goal Type Awareness)

## 1. Intent
To define the logic of Mecris's Goal Type Awareness engine as a host-agnostic WebAssembly (WASM) component. The Gemini Mandate explicitly warns: "Be vigilant about goal types (Odometer vs. Backlog). Do not allow automated pushes of 'backlog snapshots' to cumulative odometer goals." This component acts as a safety valve, validating all intended data updates to Beeminder before the Host is permitted to execute them.

## 2. The WASM vs. Host Boundary
This specification explicitly delineates the boundary between pure validation logic (The Brain) and external reality (The Host).

### 2.1 The Host's Responsibility (I/O & Reality)
The host environments (Python MCP, Go Operator) are responsible for gathering data and making API calls. The host MUST:
*   Determine the intended `datapoint_value` it wishes to send to Beeminder.
*   Fetch the Beeminder goal's configuration (specifically its `goal_type` and `current_value`).
*   Pass this data to the WASM Brain for validation.
*   Only execute the Beeminder API `POST` request if the WASM module returns `is_safe_to_push: true`.

### 2.2 The Brain's Responsibility (Pure Calculation)
The WASM Brain takes a structured JSON input of the intended push operation and the goal's context. It performs NO network calls and maintains NO internal state. It outputs a structured JSON response indicating whether the operation is safe, the validated delta, and a status message.

## 3. Functional Requirements

### FR-001: The Validation Engine Input
The Brain must accept a `ValidationRequest` JSON object containing:
*   `goal_slug` (String): The identifier for logging purposes.
*   `goal_type` (String): Must be either `"odometer"` or `"backlog"`.
*   `current_value` (Float `f64`): The current recorded value in Beeminder.
*   `intended_push_value` (Float `f64`): The raw value the Host wishes to send.

### FR-002: Odometer Validation Logic
For goals where `goal_type == "odometer"`:
*   The system must calculate the delta: `intended_push_value - current_value`.
*   If `intended_push_value < current_value` (a regression), the system MUST return `is_safe_to_push: false` to prevent data corruption.
*   If `intended_push_value >= current_value`, the system returns `is_safe_to_push: true` and includes the calculated delta.

### FR-003: Backlog Validation Logic
For goals where `goal_type == "backlog"`:
*   Backlog goals (like daily review targets) are snapshots. 
*   The system returns `is_safe_to_push: true` regardless of whether the `intended_push_value` is higher or lower than the `current_value`, because a backlog can legally decrease as tasks are completed.
*   The delta is not strictly necessary for backlog safety, but should be calculated as `current_value - intended_push_value` for diagnostic purposes.

## 4. Edge Cases

### EC-001: Unknown Goal Types
If `goal_type` is anything other than `"odometer"` or `"backlog"` (or is empty), the module MUST return `is_safe_to_push: false` (fail closed) to prevent pushing potentially catastrophic data to an improperly configured goal.

### EC-002: Zero Delta Odometer
If an odometer goal attempts to push exactly the `current_value` (`delta == 0.0`), the module returns `is_safe_to_push: false` to prevent spamming the Beeminder API with redundant data points.

## 5. Success Criteria

*   **SC-001 (Host Ignorance):** The WASM component compiles to `wasm32-unknown-unknown` (or `wasm32-wasip1`) and imports zero host functions.
*   **SC-002 (Odometer Protection):** Given an odometer goal with `current_value: 100` and an `intended_push_value: 95`, the system outputs `is_safe_to_push: false` (preventing the snapshot bug).
*   **SC-003 (Fail Closed):** Given an unrecognized goal type (e.g., `"fatbot"`), the system rejects the payload.