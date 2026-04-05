# Technical Implementation Plan: Ghost Archivist (v1.0)
**Status:** DRAFT
**Date:** 2026-04-05
**Feature ID:** SYS-001 (Ghost Archivist & Ecosystem Synchronization)

## 1. Overview
This document outlines the technical steps required to align the current Mecris codebase with the newly formalized Ghost Archivist specification (`spec.md`). The primary focus is shifting the Ghost from a "derailment prevention savior" (pushing 0.0 data) to a strict "Reality Enforcer" that runs on a continuous interval.

## 2. Architecture & Design Decisions

### 2.1 The "Continuous Reconciliation" Loop
*   **Design:** The Ghost Archivist will no longer rely on a 12-hour silence threshold or a specific 10 PM - 11:59 PM window. Instead, it will run on a scheduled interval (e.g., hourly, or specifically targeted around the day boundary).
*   **Rationale:** Aligns with the GitOps reconciliation model. It simplifies the logic and ensures reality is enforced regardless of human activity state.
*   **Component:** `ghost/archivist_logic.py` and `scheduler.py`.

### 2.2 Removal of Odometer Forgery (DEFECT-003 Resolution)
*   **Design:** The logic that pushes a `0.0` value to the Beeminder `bike` goal when no activity is detected will be completely removed.
*   **Rationale:** Beeminder naturally carries forward odometer values. Pushing artificial data violates the core principle of Reality Enforcement and pollutes the user's history.
*   **Component:** `ghost/archivist_logic.py` (`perform_archival_sync`).

### 2.3 Idempotency Enforcement
*   **Design:** The Archivist must check the current state (e.g., last synced timestamp or actual Clozemaster points) before executing API calls to prevent rate-limiting and redundant data pushes.
*   **Rationale:** Since the Ghost will run more frequently (interval-based), idempotency is critical to preserve efficiency (SC-004).
*   **Component:** `ghost/archivist_logic.py` and `services/language_sync_service.py`.

## 3. Implementation Steps (The "How")

### Phase 1: Rip Out the "Savior" Logic (DEFECT-003)
1.  **Target:** `ghost/archivist_logic.py` -> `perform_archival_sync(user_id)`
2.  **Action:** Locate the "Physical Activity Sync (The Ghost Heartbeat)" section.
3.  **Action:** Remove the `beeminder_client.add_datapoint("bike", 0.0, ...)` call entirely. The Ghost should *only* sync actual activity (which is handled elsewhere by the walk ingestion pipeline) or Language stats.
4.  **Action:** If logging inactivity is required (SC-001), ensure it is logged only to Neon (`autonomous_turns` or a dedicated log), not pushed to Beeminder as a metric.

### Phase 2: Refactor Triggers for Continuous Reconciliation
1.  **Target:** `ghost/archivist_logic.py` -> `should_ghost_wake_up(...)`
2.  **Action:** Remove the `SILENCE_THRESHOLD_SECONDS` check. The Ghost should evaluate state regardless of recent human activity.
3.  **Action:** Remove the `NIGHT_WINDOW_START/END` checks. 
4.  **Action:** Implement an idempotency check based on the last successful sync time vs. the current time, ensuring the heavy lifting (API scraping) only happens when necessary (e.g., once every X hours, or specifically when a day boundary is approaching).

### Phase 3: Scheduler Alignment
1.  **Target:** `scheduler.py` -> `_global_archivist_job`
2.  **Action:** Review the cron schedule for this job. Ensure it runs frequently enough to act as a reliable continuous reconciler (e.g., every hour, or every 15 minutes as currently defined, but guarded by the new idempotency checks in Phase 2).

### Phase 4: Observability & Metric Tracking
1.  **Target:** `usage_tracker.py` / Neon DB
2.  **Action:** Ensure that every run of the Ghost Archivist logs its outcome (Success, No-Op due to idempotency, or Failure) to the `autonomous_turns` table to satisfy SC-002 (Bot Workflow Reliability tracking, though this applies more to the `mecris-bot`, the Ghost should have similar observability).

## 4. Testing Strategy
*   **Unit Tests:** Create/update tests for `should_ghost_wake_up` to verify it fires based on idempotency rules rather than silence/time-of-day.
*   **Integration Tests:** Verify that calling `perform_archival_sync` does *not* result in a Beeminder API call for the `bike` goal if no activity occurred.
*   **Manual Verification:** Run the local MCP server, let the scheduler trigger the archivist job, and verify via logs that it correctly evaluates state and exits without pushing fake data.

## 5. Future Considerations (Out of Scope for this Plan)
*   **DEFECT-001 (Cloud Fallback Failure):** Solving the OIDC/Master Key injection for the Spin WASM deployment is deferred to a separate, dedicated infrastructure planning session.
*   **Logic Consolidation (SC-004):** Porting the newly cleaned `archivist_logic.py` to WASM via `componentize-py` is deferred until the Python implementation is proven perfectly stable in production.
