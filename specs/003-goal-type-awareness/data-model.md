# Phase 1: Data Model (Goal Type Awareness)

## Entities

### `ValidationRequest`
*   `goal_slug` (String): Diagnostic identifier.
*   `goal_type` (String): The strictly typed goal classification (`"odometer"`, `"backlog"`).
*   `current_value` (Float `f64`): The API's current reading.
*   `intended_push_value` (Float `f64`): The raw data point the Host wants to push.

### `ValidationResult`
*   `is_safe_to_push` (Boolean): The master gatekeeper.
*   `validated_delta` (Float `f64`): Diagnostic offset.
*   `status_message` (String): Diagnostic message explaining the decision.

## State Transitions (Safety Matrix)
*   **Odometer + Regression**: If `intended_push_value < current_value` -> `false` ("Regression detected").
*   **Odometer + Redundant**: If `intended_push_value == current_value` -> `false` ("Zero delta redundant").
*   **Odometer + Valid**: If `intended_push_value > current_value` -> `true` ("Safe to push odometer").
*   **Backlog**: Any inputs -> `true` ("Safe to push backlog snapshot").
*   **Unknown Type**: Any inputs -> `false` ("Unknown goal type: fail closed").
