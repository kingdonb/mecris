# Feature Specification: Majesty Cake (v1.0)
**Status:** DRAFT (Reverse-Engineered from Session Logs)
**Date:** 2026-04-05
**Feature ID:** SYS-003 (Daily Aggregate Status & Reward)

## 1. Intent
The Majesty Cake is a "celebration" engine that unifies disparate goal modalities into a single daily achievement score. It provides a visual and cognitive reward for completing all primary daily tasks (Steps, Arabic, Greek).

## 2. Logic & Aggregation

### 2.1 The Daily Aggregate Score
*   **Calculation**: A simple `X/Y` score where `X` is the number of satisfied goals and `Y` is the total number of tracked daily goals.
*   **Goal Set**: Currently includes "bike" (Steps/Walk), "Arabic Review Pump", and "Greek Review Pump".
*   **Satisfaction Check**:
    *   **Walk**: Checked via `get_cached_daily_activity`.
    *   **Languages**: Checked via `get_language_velocity_stats` (`goal_met` flag).

### 2.2 The "All Clear" Signal
*   **Trigger**: When `X == Y`.
*   **Output**: A specific "Majesty Cake" emoji (🎂) and a celebratory recommendation in the narrator context.

## 3. Modality Integration

### 3.1 Python MCP
*   **`get_daily_aggregate_status`**: A dedicated tool that returns the raw score and `all_clear` status.
*   **`get_narrator_context`**: Integrates the aggregate score into its recommendations array, prioritizing the "All Clear" celebration if achieved.

### 3.2 Android App
*   **Widget**: A home-screen fragment that displays the `X/Y` counter and triggers a celebratory animation when the aggregate score hits 100%.

## 4. Success Criteria
*   **SC-001**: The aggregate status correctly reflects the completion state of all three primary goals.
*   **SC-002**: The `all_clear` flag is only True when every tracked goal is satisfied.
*   **SC-003**: The narrator context surfaces the celebration at the very top of the recommendations list when complete.
