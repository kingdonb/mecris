# Task Breakdown: The Nag Ladder (Escalation Engine)

**Branch**: `002-nag-ladder` | **Date**: 2026-04-07 | **Spec**: [link]

## Phase 1: Setup & Scaffolding
- [x] 1.1: Initialize the Rust project in `mecris-go-spin/nag-engine-rs/`. Configure `Cargo.toml` for `cdylib` and add dependencies (`extism-pdk`, `serde`, `serde_json`).
- [x] 1.2: Define the JSON serializable structs (`Goal`, `NagRequest`, `NagResult`) in `src/lib.rs` according to the `data-model.md`.

## Phase 2: Core Logic Implementation
- [x] 2.1: Implement the Extism plugin entrypoint (`#[plugin_fn] pub fn nag_ladder(input: String) -> FnResult<String>`).
- [x] 2.2: Implement sleep window enforcement (suppress Tier 1 and Tier 2 between 22:00 and 07:00 local time).
- [x] 2.3: Implement Tier 1 (Gentle) logic: trigger if daily task incomplete, not in sleep window, and no global cooldown.
- [x] 2.4: Implement Tier 2 (Escalated) logic: trigger if Tier 1 condition met AND `idle_hours > 6.0`. Update `template_id` to escalated variant.
- [x] 2.5: Implement Tier 3 (Emergency) logic: trigger if any goal's `runway_hours < 2.0`. Ensure this overrides sleep window and cooldown.
- [x] 2.6: Implement priority ordering logic: ensure output returns Tier 3 > Tier 2 > Tier 1 if multiple triggers exist.

## Phase 3: Testing & Verification
- [x] 3.1: Write unit tests for Sleep Window logic (edge cases at exactly 22:00 and 07:00, and 03:00 suppression).
- [x] 3.2: Write unit tests for Tier 3 emergency override (ensuring it fires even with global cooldown and during sleep window).
- [x] 3.3: Write unit tests for Tier 1 vs Tier 2 boundary (idle_hours = 6.0 vs 6.1).
- [x] 3.4: Write unit tests for Priority Ordering (multiple goals in different states).
- [x] 3.5: Run `cargo test` and ensure all logic passes the Harsh Reality Check without requiring host mock servers.
