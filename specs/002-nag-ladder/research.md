# Phase 0: Research (The Nag Ladder)

## Extism vs WIT
*   **Decision**: Extism PDK
*   **Rationale**: Extism provides the simplest JSON-in, JSON-out bridge across our multiple host languages (Go, Python, Kotlin, Rust) without requiring complex WIT interface generation during the Vanguard phase.
*   **Alternatives considered**: WebAssembly Component Model (WIT). WIT is cleaner structurally but currently lacks stable cross-platform host bindings for our specific mix of languages (e.g., Kotlin).

## Timezone Handling
*   **Decision**: Host provides `current_hour_local`
*   **Rationale**: WASM cannot natively access the system clock reliably, and dealing with IANA timezone databases inside a WASM bundle inflates binary size unnecessarily. The host can easily resolve UTC to local hour before invoking the Brain.
*   **Alternatives considered**: Passing UTC time and timezone string to WASM.

## Threshold Boundary Logic
*   **Decision**: Strict inequalities (`< 2.0`, `> 6.0`)
*   **Rationale**: Enforces deterministic boundaries without edge-case flapping.
*   **Alternatives considered**: `<=` or `>=` which can lead to premature emergency alerts at exactly 2.0 hours.
