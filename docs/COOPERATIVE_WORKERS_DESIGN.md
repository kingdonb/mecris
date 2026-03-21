# Cooperative Co-Authorizing Background Workers

## 1. Introduction & The Pivot
Relying on external crons (like GitHub Actions or Fermyon's gated `spin aka` service) to act as a "Cloud Brain" masks underlying unreliability in the primary systems. The user has two powerful, active systems:
1. **The Android Phone** (Mecris-Go App)
2. **The Local Laptop** (Python MCP Server)

Instead of relying on a 3rd party to watch them, they should watch each other. This establishes a **Cooperative and Co-Authorizing** architecture. As long as *one* of these devices is active, the system remains highly available and self-healing.

## 2. The Shared Ledger (Neon DB)
Both workers need a place to "check in." We will expand the existing `scheduler_election` table in the Neon database to serve as a universal heartbeat ledger.

**Current Schema:**
`role` ('leader'), `process_id`, `heartbeat`

**Proposed Schema Updates:**
We treat `role` as the component identifier:
- `mcp_server`: The Python backend.
- `android_client`: The Android background worker.

## 3. Worker Responsibilities

### 3.1 The Android Worker (`WalkHeuristicsWorker`)
**Current State:** Runs every 15 minutes to check Health Connect and sync steps.
**New Cooperative Duties:**
1. **Heartbeat:** When the worker runs, it hits the Spin API (`/health` or a new `/heartbeat` endpoint) to register that Android is alive.
2. **Monitor MCP:** The Spin API response will include `mcp_server_active` (boolean, true if MCP checked in within the last 90 minutes).
3. **Failover Execution:** If `mcp_server_active` is `false` (meaning the laptop lid is closed), the Android App assumes the mantle of "Failover Trigger" and fires an HTTP POST to `/internal/failover-sync` on the Spin API.
   * *Result: The Cloud Brain scrapes Clozemaster and protects Beeminder because the phone told it to.*

### 3.2 The Python MCP Worker (`scheduler.py`)
**Current State:** Runs an `asyncio` loop handling reminders, walk syncs, and language syncs.
**New Cooperative Duties:**
1. **Heartbeat:** Continuously updates the `mcp_server` role in the `scheduler_election` table to prove it is alive.
2. **Monitor Android:** Checks the `android_client` heartbeat.
3. **Dead-Man's Switch Alert:** If the `android_client` heartbeat is older than 4 hours, the MCP server autonomously sends a Twilio SMS to the user:
   * *"Hey, I haven't heard from your phone's background worker in 4 hours. Did you force-close the app? Open Mecris-Go so I can see your steps!"*

## 4. Why This is Better
1. **No External Dependencies:** We drop the need for GitHub Actions, cron-job.org, or Akamai Functions.
2. **Self-Healing:** If Android gets Doze-mode killed, Python texts the user to revive it. If Python gets suspended (laptop closed), Android silently triggers the cloud fallback.
3. **True Autonomy:** The system doesn't just run blindly; it possesses self-awareness of its own distributed components.

## 5. Implementation Plan (TDG)
- [ ] **Phase 1: Spin API Expansion**: Create `/heartbeat` endpoint in Rust to upsert the caller's role (`android_client`) and return the status of the `mcp_server`.
- [ ] **Phase 2: Android Intelligence**: Update `WalkHeuristicsWorker.kt` to ping the heartbeat endpoint and conditionally call the failover trigger.
- [ ] **Phase 3: Python Dead-Man's Switch**: Update `scheduler.py` to monitor the Android heartbeat and dispatch Twilio alerts if it goes dark.
