# Implementation Plan: The Nag Ladder (Escalation Engine)

**Branch**: `002-nag-ladder` | **Date**: 2026-04-07 | **Spec**: [link]
**Input**: Feature specification from `/specs/002-nag-ladder/spec.md`

## Summary

The Nag Ladder pure-logic WASM engine takes goal status and idle time via JSON and deterministically outputs a notification tier. This fulfills the requirement to decouple pure calculation from Host environment side-effects (Twilio, Neon DB) per the Zero-Split-Brain architecture.

## Technical Context

**Language/Version**: Rust 1.75
**Primary Dependencies**: Extism / serde_json
**Storage**: None
**Testing**: cargo test
**Target Platform**: WASM (wasm32-unknown-unknown / wasm32-wasip1)
**Project Type**: WebAssembly Component (WASM)
**Performance Goals**: < 1ms execution time
**Constraints**: Pure math function, NO network access, NO disk I/O, NO host functions
**Scale/Scope**: Very small footprint, highly cacheable WASM binary.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

*   **Zero-Split-Brain**: PASS. Logic is in pure WASM.
*   **Host Boundary**: PASS. WASM module performs zero network requests. The Host handles API fetching and time.
*   **TDG / HCAT**: PASS. Cargo tests will assert behavior without needing a host execution environment.

## Project Structure

### Documentation (this feature)

```text
specs/002-nag-ladder/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (next step)
```

### Source Code (repository root)

```text
mecris-go-spin/
└── nag-engine-rs/
    ├── Cargo.toml
    ├── src/
    │   └── lib.rs       # The Extism plugin logic
    └── tests/           # Deterministic cargo tests
```

## Complexity Tracking

N/A - Adheres strictly to established architectural boundaries. No violations or unnecessary complexity detected.