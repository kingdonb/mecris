# Task Breakdown: The Review Pump (Zero-Split-Brain Core)

**Branch**: `001-review-pump-core` | **Date**: 2026-04-07 | **Spec**: [link]

## Phase 1: Setup & Scaffolding
- [ ] 1.1: Initialize the Rust project in `mecris-go-spin/review-pump-rs/`. Configure `Cargo.toml` for `cdylib` and add dependencies (`extism-pdk`, `serde`, `serde_json`).
- [ ] 1.2: Define the JSON serializable structs (`PumpRequest`, `PumpResult`) in `src/lib.rs` according to the `data-model.md`.

## Phase 2: Core Logic Implementation
- [ ] 2.1: Implement the Extism plugin entrypoint (`#[plugin_fn] pub fn calculate_pump(input: String) -> FnResult<String>`).
- [ ] 2.2: Implement Error Boundary fallback logic (if JSON deserialization fails, return a valid JSON payload indicating an Error status).
- [ ] 2.3: Implement "Cavitation" Edge Case logic (`current_backlog <= 0`). Return `required_clearance = base_daily_target` and set status to "Cavitation".
- [ ] 2.4: Implement "Maintenance Mode" logic (`pump_multiplier <= 1.0`). Return `required_clearance = base_daily_target` and set status to "Maintenance".
- [ ] 2.5: Implement "Active Pumping" logic using `f64` precision. Calculate `required_clearance = base_daily_target + ceil(current_backlog * (pump_multiplier - 1.0) * 0.10)`.

## Phase 3: Testing & Verification
- [ ] 3.1: Write unit tests for the "Maintenance Mode" formula (ensuring `f64` multipliers like `1.0` don't trigger active pumping logic).
- [ ] 3.2: Write unit tests for "Active Pumping" demonstrating that mathematical progress occurs properly due to `f64` precision and `ceil()` (e.g., `current_backlog = 5`, `multiplier = 1.5`, should yield `base_target + 1`).
- [ ] 3.3: Write unit tests for the "Cavitation" edge case (ensuring negative backlogs don't reduce daily requirements below baseline).
- [ ] 3.4: Write unit tests ensuring that malformed JSON strings return a valid fallback state instead of panicking.
- [ ] 3.5: Run `cargo test` and verify strict zero-host independence and determinism.
