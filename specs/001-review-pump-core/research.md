# Phase 0: Research (The Review Pump)

## Mathematical Precision
*   **Decision**: Use `f64` for all multiplier calculations, then `ceil()` to nearest integer.
*   **Rationale**: Multipliers like `1.5` or `0.10` inherently introduce floating-point math. Truncating to integers too early could lead to the pump stalling (e.g., if `(5 * 0.1) = 0.5` truncates to `0`). Using `f64` ensures precision before final rounding guarantees progress.
*   **Alternatives considered**: Pure integer arithmetic (e.g., multiplier `150` instead of `1.5`). Discarded because `f64` aligns more cleanly with JSON payload standards and human-readable settings.

## Error Handling Boundary
*   **Decision**: Graceful fallback values on invalid input (e.g., malformed JSON).
*   **Rationale**: If the WASM Brain panics, the Host (Operator/API) might crash or throw unhandled 500 errors. It is better for the WASM to return a valid JSON payload indicating an error state, or fall back to `required_clearance = base_daily_target` and `pump_status = "Error"`.
*   **Alternatives considered**: Panicking on `unwrap()`. Discarded as it violates robust architecture principles.
