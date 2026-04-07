# Feature Specification: The Majesty Cake (Aggregate Status)
**Status:** DRAFT
**Date:** 2026-04-07
**Feature ID:** CORE-003 (The Majesty Cake)

## 1. Intent
To define the logic of Mecris's daily aggregate status widget (The Majesty Cake) as a host-agnostic WebAssembly (WASM) component. This component must deterministically calculate a unified "All Clear" celebration state by evaluating the completion status of all active daily modalities (Steps, Arabic, Greek).

## 2. The WASM vs. Host Boundary
This specification explicitly delineates the boundary between the pure aggregation logic (The Brain) and external reality (The Host).

### 2.1 The Host's Responsibility (I/O & Reality)
The host environments are responsible for data gathering. The host MUST:
*   Fetch the current daily completion status for the physical modality (Dog Walks) from the Neon Database (populated by the Android Bridge).
*   Fetch the current daily completion status for the language modalities (Arabic, Greek) from their respective trackers (e.g., Clozemaster sync results or Review Pump targets).
*   Provide the aggregated goal states as a JSON payload to the WASM module.
*   Render the output (e.g., in the CLI, via an SMS summary, or the Android UI widget).

### 2.2 The Brain's Responsibility (Pure Calculation)
The WASM Brain takes a structured JSON input of current goal states. It performs NO network calls and maintains NO internal state. It outputs a structured JSON response indicating the aggregate progress (X out of Y goals completed), whether the "All Clear" condition is met, and a specific celebratory or encouraging message template ID.

## 3. Functional Requirements

### FR-001: The Aggregation Engine Input
The Brain must accept an `AggregateRequest` JSON object containing:
*   `goals`: Array of objects `{ slug: String, is_required_today: Boolean, is_completed: Boolean }`

### FR-002: Aggregate Calculation
The engine must calculate the total number of required goals (`Y`) and the total number of completed required goals (`X`).
*   It must output an `AggregateResult` JSON object containing:
    *   `completed_count` (Integer): `X`
    *   `required_count` (Integer): `Y`
    *   `all_clear` (Boolean): True if `X == Y` and `Y > 0`. False otherwise.
    *   `status_message` (String): A human-readable summary (e.g., "2/3 goals satisfied.").

### FR-003: The "All Clear" Celebration
If `all_clear` is true, the engine must return a specific `template_id` or flag indicating that the "Majesty Cake" celebration should be triggered by the Host.

## 4. Edge Cases

### EC-001: No Required Goals
If `required_count == 0` (e.g., a rest day where no goals are required), the `all_clear` flag should default to `false` to avoid unearned celebrations, or optionally `true` if configured for "rest day" celebrations. The specification mandates `false` to ensure the Majesty Cake is a reward for active effort.

### EC-002: Missing Data
If a required goal's status is unknown (missing data), it must be treated as `is_completed: false`.

## 5. Success Criteria

*   **SC-001 (Host Ignorance):** The WASM component compiles to `wasm32-unknown-unknown` (or `wasm32-wasip1`) and imports zero host functions for network or disk access.
*   **SC-002 (Deterministic Aggregation):** Given an array of 3 required goals where 2 are completed, the output deterministically states `completed_count: 2, required_count: 3, all_clear: false`.
*   **SC-003 (The Cake is Earned):** The `all_clear` flag is ONLY true when all required goals are explicitly marked as completed.