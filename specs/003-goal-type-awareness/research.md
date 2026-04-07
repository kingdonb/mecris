# Phase 0: Research (Goal Type Awareness)

## Odometer vs Backlog Parsing
*   **Decision**: Exact string matching on the `goal_type` enum (`"odometer"`, `"backlog"`).
*   **Rationale**: Avoids clever heuristics. If Beeminder adds a new goal type tomorrow (e.g. `"fatbot"` or `"do_more"`), the engine must fail closed (`is_safe_to_push: false`). This is a safety valve; strict string validation guarantees we don't accidentally apply backlog logic to an unknown goal type.

## Delta Calculation Representation
*   **Decision**: Calculate delta but prioritize boolean safety flag.
*   **Rationale**: The Host needs to know the exact delta for logging, but the primary return value is the `is_safe_to_push` boolean. For `odometer`, `delta = intended - current`. For `backlog`, `delta = current - intended`. We standardize the JSON response to return a positive float delta for logging purposes, but the boolean is the strict gatekeeper.
