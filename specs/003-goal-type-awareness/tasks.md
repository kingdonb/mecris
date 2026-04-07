# Task Breakdown: Goal Type Awareness (The Safety Valve)

**Branch**: `003-goal-type-awareness` | **Date**: 2026-04-07 | **Spec**: [link]

## Phase 1: Setup & Scaffolding
- [x] 1.1: Initialize the Rust project in `mecris-go-spin/goal-type-rs/`. Configure `Cargo.toml` for `cdylib` and add dependencies (`extism-pdk`, `serde`, `serde_json`).
- [x] 1.2: Define the JSON serializable structs (`ValidationRequest`, `ValidationResult`) in `src/lib.rs` according to the `data-model.md`.

## Phase 2: Core Logic Implementation
- [x] 2.1: Implement the Extism plugin entrypoint (`#[plugin_fn] pub fn validate_push(input: String) -> FnResult<String>`).
- [x] 2.2: Implement Error Boundary fallback logic (if JSON deserialization fails, return `is_safe_to_push: false`).
- [x] 2.3: Implement strict matching on `goal_type` enum. Any unexpected string immediately fails closed (`false`).
- [x] 2.4: Implement Odometer logic: calculate `intended - current`. Reject regressions and zero-deltas (`false`). Accept positive progress (`true`).
- [x] 2.5: Implement Backlog logic: calculate `current - intended`. Always return `true`.

## Phase 3: Testing & Verification
- [x] 3.1: Write unit tests for Odometer regressions and redundant pushes (ensuring they correctly block the push).
- [x] 3.2: Write unit tests for valid Odometer progress (ensuring it permits the push).
- [x] 3.3: Write unit tests for Backlog snapshots (ensuring both increases and decreases are permitted).
- [x] 3.4: Write unit test for unrecognized goal types (ensuring they fail closed).
- [x] 3.5: Run `cargo test` and verify strict zero-host independence and determinism.
