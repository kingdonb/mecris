# Task Breakdown: The Majesty Cake (Aggregate Status)

**Branch**: `004-majesty-cake` | **Date**: 2026-04-07 | **Spec**: [link]

## Phase 1: Setup & Scaffolding
- [x] 1.1: Initialize the Rust project in `mecris-go-spin/majesty-cake-rs/`. Configure `Cargo.toml` for `cdylib` and add dependencies (`extism-pdk`, `serde`, `serde_json`).
- [x] 1.2: Define the JSON serializable structs (`GoalStatus`, `AggregateRequest`, `AggregateResult`) in `src/lib.rs` according to the `data-model.md`.

## Phase 2: Core Logic Implementation
- [x] 2.1: Implement the Extism plugin entrypoint (`#[plugin_fn] pub fn aggregate_status(input: String) -> FnResult<String>`).
- [x] 2.2: Implement logic to parse the `AggregateRequest` JSON and iterate over the `goals` array.
- [x] 2.3: Implement calculation for `required_count` (sum of goals where `is_required_today == true`).
- [x] 2.4: Implement calculation for `completed_count` (sum of goals where `is_required_today == true` and `is_completed == true`).
- [x] 2.5: Implement logic to determine `all_clear` state (true only if `required_count > 0` and `completed_count == required_count`).
- [x] 2.6: Format and return the `AggregateResult` JSON payload, including the dynamically generated `status_message` (e.g., "X/Y goals satisfied.") and setting `template_id` if `all_clear` is true.

## Phase 3: Testing & Verification
- [x] 3.1: Write unit tests for "Pending" state (e.g., 1 of 3 required goals completed).
- [x] 3.2: Write unit tests for "All Clear" state (e.g., 3 of 3 required goals completed).
- [x] 3.3: Write unit tests for "Rest Day" edge case (`required_count == 0`), ensuring `all_clear` remains false.
- [x] 3.4: Write unit tests to verify that `is_completed` status is ignored if `is_required_today` is false (optional goals don't affect the core count or block the cake).
- [x] 3.5: Run `cargo test` and ensure all pure-math aggregation logic passes the Harsh Reality Check without requiring host API mocks.
