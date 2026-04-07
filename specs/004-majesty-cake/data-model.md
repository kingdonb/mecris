# Phase 1: Data Model (The Majesty Cake)

## Entities

### `GoalStatus`
*   `slug` (String): Identifier (e.g., 'arabic', 'steps', 'greek'). Ignored by calculation logic, kept for logging/tracing.
*   `is_required_today` (Boolean): True if the goal is active and expected to be completed today.
*   `is_completed` (Boolean): True if the user has successfully met the requirement today.

### `AggregateRequest`
*   `goals` (Array of `GoalStatus`): Current daily state of all modalities tracked by the Host.

### `AggregateResult`
*   `completed_count` (Integer): Sum of `GoalStatus` where `is_required_today == true` AND `is_completed == true`.
*   `required_count` (Integer): Sum of `GoalStatus` where `is_required_today == true`.
*   `all_clear` (Boolean): True if `required_count > 0` AND `completed_count == required_count`. False otherwise.
*   `status_message` (String): Diagnostic string (e.g., "2/3 goals satisfied.").
*   `template_id` (String | Null): Identifier for the celebratory "Majesty Cake" template to dispatch if `all_clear` is true.

## State Transitions
*   **Pending**: `completed_count < required_count`. `all_clear` remains `false`.
*   **All Clear**: `completed_count == required_count` AND `required_count > 0`. `all_clear` transitions to `true`.
*   **Rest Day**: `required_count == 0`. `all_clear` defaults to `false`.
