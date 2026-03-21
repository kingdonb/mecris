# 🧠 Mecris Architecture: The Nervous System

This document maps the asynchronous flows and data pathways of the Mecris accountability system.

## 1. The Walk Telemetry Pipeline
Tracing a "Walk" from the hardware sensor to the accountability ledger.

1.  **Sensor Capture (Android):** 
    - Google Fit/Health Connect captures steps and GPS routes.
    - **Issue:** Configuration issues (Location off) can degrade data quality without triggering permission errors.
2.  **Local Heuristic (Android):**
    - `HealthConnectManager.kt` performs native deduplication via the Aggregate API.
    - `WalkHeuristicsWorker.kt` (Periodic Work) polls every 15 minutes.
    - If `steps > 1500` or `sessions > 0`, it infers a "Walk."
3.  **The Cloud Sync (Neural Link):**
    - `MainActivity.kt` (or the background worker) pushes to the **Spin Backend** via OIDC-authenticated POST to `/walks`.
    - Data quality diagnostics (Distance vs Steps) are attached to this payload.
4.  **Backend Persistence (Spin/Neon):**
    - The Spin (Go/Rust) backend validates the OIDC token via PocketID.
    - Data is stored in the **Neon PostgreSQL** `walk_inferences` table, strictly scoped by `user_id`.
5.  **Accountability Bridge (Python MCP):**
    - The Python MCP server calls `get_cached_daily_activity(user_id)`.
    - It checks both the Neon Cloud and Beeminder API for that specific user.
    - **Timezone Lock:** All components are now synchronized to `America/New_York` midnight for "Today" resets.

## 2. The Review Pump (Language Debt)
1.  **Extraction:** `scripts/clozemaster_scraper.py` performs a headless login simulation to Clozemaster.
2.  **Forecasting:** It extracts "Ready for Review" counts for Arabic and Greek, including Tomorrow and 7-day liabilities.
3.  **Velocity Engine:** The MCP tool `get_language_velocity_stats` calculates the *Clearance Velocity* (cards/day) required to hit 0 reviews by Friday.

## 3. The Autonomous Pulse (Scheduler)
1.  **Leader Election:** `scheduler.py` uses Neon/PostgreSQL to elect a single "Leader" process **per user** across distributed instances.
2.  **Heartbeat:** The Leader process performs periodic checks (Reminders, Budget updates) scoped by `user_id`.
3.  **Visibility:** The `system_pulse` field in `get_narrator_context` allows any agent to verify scheduler health for the active user.

## 4. Hierarchy of Data Quality
- **L1 (Critical):** Step Count (Passive, high reliability).
- **L2 (Significant):** Exercise Sessions (Intentional activity).
- **L3 (High-Fidelity):** GPS Routes (Verified outdoor movement).
- **L4 (Deep Insight):** Heart Rate/Intensity (Future expansion).

## 5. State Divergence & Conflict Resolution
The system maintains a dual-track state (Cloud vs Ledger).

- **The Source of Truth (Neon Cloud):** The PostgreSQL `walk_inferences` contains the highest-fidelity raw telemetry received from the Android device, isolated by `user_id`.
- **The Ledger (Beeminder):** Contains the official "Accountability Points" that drive the derailment logic.
- **Conflict Resolution (Python MCP):** 
    - When `get_cached_daily_activity` is called, it queries both Neon and Beeminder.
    - **Inertia Strategy:** If Neon has a "Inferred Walk" but Beeminder is missing a datapoint, the status is marked as `completed` (Heuristic match). 
    - **Self-Healing:** Background worker automatically pushes pending Neon walks to Beeminder for each user.

---
*Last Updated: March 21, 2026*
