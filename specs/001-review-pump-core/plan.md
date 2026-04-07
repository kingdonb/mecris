# Implementation Plan: The Review Pump (Zero-Split-Brain Core)

**Branch**: `001-review-pump-core` | **Date**: 2026-04-07 | **Spec**: [link]
**Input**: Feature specification from `/specs/001-review-pump-core/spec.md`

## Summary

The Review Pump math engine calculates daily required clearance targets based on backlog size and a user-controlled intensity multiplier. It is encapsulated as a pure WASM component using Extism, guaranteeing deterministic math across all host platforms without external dependencies.

## Technical Context

**Language/Version**: Rust 1.75
**Primary Dependencies**: Extism / serde_json
**Storage**: None
**Testing**: cargo test
**Target Platform**: WASM (wasm32-unknown-unknown / wasm32-wasip1)
**Project Type**: WebAssembly Component (WASM)
**Performance Goals**: < 1ms execution time
**Constraints**: Pure math function, NO network access, NO disk I/O, NO host functions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

*   **Zero-Split-Brain**: PASS. Logic is in pure WASM.
*   **Host Boundary**: PASS. WASM module performs zero network requests. The Host handles API fetching and time.
*   **TDG / HCAT**: PASS. Cargo tests will assert behavior without needing a host execution environment.

## Project Structure

### Documentation (this feature)

```text
specs/001-review-pump-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (next step)
```

### Source Code (repository root)

```text
mecris-go-spin/
└── review-pump-rs/
    ├── Cargo.toml
    ├── src/
    │   └── lib.rs       # The Extism plugin logic
    └── tests/           # Deterministic cargo tests
```

## Complexity Tracking

N/A - Directly implements the constitutional requirement for WASM math engines without introducing architectural divergence.
