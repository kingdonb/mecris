# Phase 1: Data Model (The Review Pump)

## Entities

### `PumpRequest`
*   `current_backlog` (Integer): Total pending reviews across all languages.
*   `pump_multiplier` (Float `f64`): The intensity lever (e.g., 1.0, 2.0, 4.0, 10.0).
*   `base_daily_target` (Integer): The minimum baseline daily goal (e.g., 100).

### `PumpResult`
*   `required_clearance` (Integer): Calculated target to hit today.
*   `is_goal_met` (Boolean): True if current progress >= required_clearance.
*   `pump_status` (String): Diagnostic status ("Maintenance", "Active", "Cavitation", "Error").

## State Transitions (Formulas)
*   **Maintenance Mode**: If `pump_multiplier <= 1.0`, then `required_clearance = base_daily_target`.
*   **Active Pumping**: If `pump_multiplier > 1.0`, then `required_clearance = base_daily_target + ceil(current_backlog * (pump_multiplier - 1.0) * 0.10)`.
*   **Cavitation (Dry Pump)**: If `current_backlog <= 0`, revert to Maintenance Mode formula but set `pump_status` to "Cavitation".
