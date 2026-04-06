# Feature Specification: Harmonious Discord (v1.0)
**Status:** RATIFIED
**Date:** 2026-04-05
**Feature ID:** SYS-005 (The Jet-Propelled DMZ)

## 1. Intent
To resolve the conflict between high-speed iteration (Python) and high-performance execution (Rust) by allowing both to coexist in a self-validating, "jet-propelled" architecture.

## 2. The Components

### 2.1 The Source (Python Vanguard)
*   **Role**: High-level specification. 
*   **Priority**: Logic integrity. 
*   **Deployment**: WASM via `componentize-py`.
*   **Endpoints**: Postfixed with `-py` (e.g., `/internal/nag-check-py`).

### 2.2 The Jet (Rust Iron Core)
*   **Role**: Optimized native implementation.
*   **Priority**: Speed, memory safety, battery efficiency.
*   **Deployment**: Compiled Rust WASM.
*   **Endpoints**: Postfixed with `-rs` (e.g., `/internal/nag-check-rs`).

## 3. Shadow Execution (The Jet Pattern)
The primary system (e.g., `sync-service`) must treat the Rust implementation as a "Jet" for the Python source:
1.  **Execute Jet**: Call the Rust implementation for the user-facing response.
2.  **Shadow Source**: Sequentially or asynchronously call the Python implementation.
3.  **Validate**: Compare results.
4.  **Log Divergence**: If `Jet != Source`, insert a record into the `jet_divergence` table.

## 4. Success Criteria
*   **SC-001**: System returns Rust-speed responses (< 10ms) while still performing Python-level validation.
*   **SC-002**: Architectural drift is detected automatically via the `jet_divergence` log.
*   **SC-003**: 100% of core features (Review Pump, Nag Engine, Budget Governor) are supported by both implementations.

## 5. User Scenarios
*   **US-001**: As a developer, I can change logic in Python first to "spec" a new behavior, then "jet" it in Rust once the behavior is stable.
*   **US-002**: As an operator, I can query the `jet_divergence` table to see if our optimized core is still faithful to our logical soul.
