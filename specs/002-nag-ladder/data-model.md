# Phase 1: Data Model (The Nag Ladder)

## Entities

### `Goal`
*   `slug` (String): Identifier (e.g., 'arabic', 'steps')
*   `is_completed` (Boolean): True if goal is satisfied for the day
*   `runway_hours` (Float): Time until derailment

### `NagRequest`
*   `goals` (Array of `Goal`): Current state of all active goals
*   `idle_hours` (Float): Hours since last user interaction
*   `current_hour_local` (Integer): Current hour (0-23) in user's timezone
*   `global_cooldown_active` (Boolean): True if a message was sent recently

### `NagResult`
*   `should_send` (Boolean): True if the host must dispatch a message
*   `tier` (Integer): Escalation level (1 = Gentle, 2 = Escalated, 3 = Emergency)
*   `template_id` (String): Identifier for the message template to use

## State Transitions
*   **Gentle to Escalated**: If `idle_hours > 6.0` and goal is not met.
*   **Escalated to Gentle**: If user interacts, `idle_hours` resets to 0.0.
*   **Any to Emergency**: If `runway_hours < 2.0`, immediately overrides constraints.
