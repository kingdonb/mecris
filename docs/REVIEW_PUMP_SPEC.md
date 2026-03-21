# Design Spec: The Review Pump Lever

## Overview
The "Review Pump" is a mechanism to manage language review backlogs (e.g., Clozemaster). It calculates a daily "Flow Rate" (velocity) required to clear debt based on a user-selected "Lever" (multiplier).

## The Lever Spectrum
The Lever determines the `BacklogClearanceRate` (BCR), which is the number of days over which the current debt should be eliminated.

| Setting | Name | Backlog Clearance Days | Formula |
|---------|------|------------------------|---------|
| 1x      | Maintenance | N/A (Infinite) | `tomorrow_liability` |
| 2x      | Steady Progress | 14 Days | `tomorrow_liability + (current_debt / 14)` |
| 4x      | Aggressive | 5 Days | `tomorrow_liability + (current_debt / 5)` |
| 10x     | The Blitz | 2 Days | `tomorrow_liability + (current_debt / 2)` |

## UI Widget Components
1. **The Pressure Gauge**: A visual meter showing `Current Daily Completions` vs. `Target Flow Rate`.
2. **The Multiplier Lever**: A segmented control or notched slider to set the intensity.
3. **Status Indicators**:
   - **Cavitation**: If completions < 1x rate (Backlog is growing).
   - **Laminar Flow**: If completions == Target rate.
   - **Turbulent Flow**: If completions > Target rate (Backlog clearing faster than planned).

## Technical Implementation (TDG)
1. **State Persistence**: Store the current `pump_multiplier` in the Neon DB or a local config.
2. **Logic Engine**: Update `get_language_velocity_stats` to factor in the multiplier.
3. **Tool Update**: Add `set_review_pump_lever(multiplier: float)` to the MCP server.

## Success Metric
The user clears the backlog without "doing the math," similar to the Beeminder student loan experience.
