---
name: Beeminder Audit
description: Procedural guidance on safely auditing, modifying, and cleaning up Beeminder goal data (including odometer resets, @TARE mechanics, and timezone protections) without risking accidental derailment. Triggers on keywords like beeminder audit, beeminder cleanup, delete datapoints, tare.
---
# Beeminder Audit Skill

Auditing, correcting, and backdating goal data on Beeminder carries a significant risk of accidental goal derailment. This skill provides a set of strict rules and procedures to safely audit and modify Beeminder goal data.

## Risk Profile & Safety Rules
1.  **Do Less / Ceiling Goals (Hard Cap)**:
    *   For goals like API spend limits, adding a high value in the past can trigger historical ceiling violations, immediately derailing the goal.
    *   **Always** inspect the current road parameters and historical cap levels before adding high historical values.
2.  **Do More / Floor Goals**:
    *   Deleting or moving a datapoint's date forward can create a temporary gap on that day, violating the minimum floor and triggering an immediate derailment.
    *   **Never** shift a datapoint's date forward if it was the only data point satisfying the goal on its original date.
3.  **Authentication & User-Awareness**:
    *   Always verify you are querying and writing to the correct user's Beeminder goals.
    *   Do not overwrite or delete values unilaterally without showing the current history and requesting explicit confirmation.

## The `@TARE` Reset Mechanic
For cumulative/odometer goals that reset every month (like `groqspend` or `claudespend`):
1.  **Start-of-Month Tare**:
    *   A tare datapoint of value `0.0` with the exact comment `@TARE` must be submitted on the 1st day of the month (or prior to the month's first real reading).
    *   Beeminder uses this tare to offset the visual graph, resetting the cumulative cost back to zero for the new period.
2.  **Audit Check**:
    *   Verify that each month boundary has a `0.0` value with `@TARE` comment. If missing, a reset will not be registered visually, causing the graph to display cumulative lifetime costs rather than monthly costs.

## Timezone Protection (The Daystamp Bug)
Beeminder API accepts a `daystamp` string in `YYYYMMDD` format.
1.  **Never rely on naive datetime conversions**:
    *   Converting a naive UTC datetime (like `2026-06-01 00:00:00`) to local US/Eastern timezone shifts the timestamp back by 4-5 hours (to `2026-05-31 20:00:00-04:00`), changing the daystamp and corrupting the month boundary.
2.  **Ensure explicit timezone metadata**:
    *   Always construct timezone-aware UTC datetimes at 12:00 noon UTC (e.g. `datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)`) for historical entries. When converted to Eastern, the daystamp will remain on the correct day (e.g., `20260630`).

## Audit Workflow
1.  **Fetch History**: Retrieve the last 30-40 datapoints for the goal using the `get_goal_datapoints` API tool.
2.  **Map Boundaries**: Organize readings by month and check for:
    *   Presence of `@TARE` on Day 1 of each month.
    *   Consistency of final odometer readings on the last day of each month.
    *   Timezone shifting or duplicate datapoints.
3.  **Confirm Edits with User**: Show a table of proposed changes (Deletions, Modifications, Additions) and request explicit approval.
4.  **Execute & Verify**: Perform deletions/insertions in sequence, then re-fetch the history to display the finalized audit report.
