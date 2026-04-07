# Implementation Plan: Goal Type Awareness (The Safety Valve)

**Branch**: `003-goal-type-awareness` | **Date**: 2026-04-07 | **Spec**: [link]
**Input**: Feature specification from `/specs/003-goal-type-awareness/spec.md`

## Summary

The Goal Type Awareness engine is a pure-logic WASM validation valve. It accepts intended Beeminder data points and the goal context via JSON, and strictly prevents regression bugs on cumulative (odometer) goals while safely allowing snapshot updates for backlog goals. 

## Technical Context

**Language/Version**: Rust 1.75
**Primary Dependencies**: Extism / serde_json
**Storage**: None
**Testing**: cargo test
**Target Platform**: WASM (wasm32-unknown-unknown / wasm32-wasip1)
**Project Type**: WebAssembly Component (WASM)
**Performance Goals**: < 1ms execution time
**Constraints**: Pure validation function, NO network access, NO host functions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

*   **Zero-Split-Brain**: PASS. Logic is in pure WASM.
*   **Host Boundary**: PASS. WASM module performs zero network requests. 
*   **TDG / HCAT**: PASS. Cargo tests will assert safety behaviors cleanly.

## Project Structure

### Documentation (this feature)

```text
specs/003-goal-type-awareness/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (next step)
```

### Source Code (repository root)

```text
mecris-go-spin/
└── goal-type-rs/
    ├── Cargo.toml
    ├── src/
    │   └── lib.rs       # The Extism plugin logic
    └── tests/           # Deterministic cargo tests
```

## Complexity Tracking

N/A - Directly implements the constitutional requirement for WASM logic engines.
