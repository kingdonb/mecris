# Reminder System Architecture (Phase 2 & 3)

This document captures the architectural decisions made during the April 2026 "Grill-Me" session regarding the transition of the dog-walk reminder system into an autonomous Rust-based WASM service.

## 1. Decentralized Trigger Model

### The Problem
Fermyon Spin Cloud (the host for our Rust WASM logic) is event-driven and does not natively support cron triggers. Health Connect data (steps/distance) is trapped on the Android device and must be pushed.

### The Decision (Option A + B)
Instead of relying on a fragile external cron, we use a **Cooperative Trigger** model:
- **Android as Primary Driver:** The Android app's `WalkHeuristicsWorker` detects when the local Python MCP server is offline ("CLOUD: AUTONOMOUS" mode).
- **Orchestrated Sync:** When the Android app pushes step data to `/walks` or triggers `/internal/cloud-sync`, the Spin service autonomously chains the execution into the text-reminder heuristics.
- **Server-Side Fallback:** A Python `scheduler.py` process remains the intended cron fallback for non-Android tasks (like language scraping), hitting the same endpoints via a leader-election-aware loop.

## 2. Data Integrity: AggDay=last

### The Heuristic
Early implementations attempted to `.sum()` all step records for the day. This was identified as a bug because the Android app pushes "Running Totals" from Health Connect.

### The Fix
The Rust `aggregate_step_count` logic now strictly follows the **Beeminder `AggDay=last`** paradigm. It takes the *last* valid step count reported for the day, ensuring that intermittent syncs throughout the day do not result in double or triple-counting steps.

## 3. Multi-Tenancy & Privacy (Technical Debt)

During the design review, we identified the following gaps that must be resolved to move beyond a single-user prototype:

- **Localized Weather:** Current `openweather_lat/lon` are global Spin variables. **Required Fix:** Move location coordinates to encrypted fields in the `users` table.
- **Consent Management:** The Android UI lacks a way to grant/revoke SMS authorization or manage the target phone number.
- **Auth Lifecycle:** The Android app requires a "Log Out" button and a way to re-trigger OIDC flows without an app reinstall.

## 4. Leader Election & Indirect Observation

The MCP server currently operates in **STDIO mode**, meaning the Android app cannot reach it directly. The app "observes" the health of the home server by reading the `scheduler_election` table in the Neon database.
- If a `leader` heartbeat is fresh (< 90s), Android assumes the Home Server is handling reminders.
- If the heartbeat is stale, Android assumes the "Autonomous" role and triggers the Cloud Sync itself.
