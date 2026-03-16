## 🐕 Health Data Transparency & High-Fidelity Refactor

This PR implements a comprehensive refactor of the health data synchronization and diagnostics layer, transforming the Mecris-Go app into a high-fidelity biological telemetry device (#76).

### ✅ Key Changes

#### 1. UI Hierarchy Swap (Primary Dashboard)
- **Neural Link Lead:** `MainActivity` has been refactored to host the high-fidelity dashboard (Momentum Orb, Sync status, Odometer) as the primary entry point.
- **Subordinated Tech:** OIDC login, permissions, and background worker status moved to a secondary **"System Health"** screen (accessible via Settings icon).
- **Native Navigation:** Implemented `BackHandler` to allow natural system back gestures from Settings back to the Dashboard.

#### 2. Data Quality & Diagnostic Reasoning
- **Codified Diagnostics:** `HealthConnectManager.kt` now detects specific Google Fit/Health Connect configuration issues (e.g., location tracking disabled).
- **Data Alert Banner:** A compact warning banner appears on the dashboard only when quality is degraded, linking directly to the resolution screen.
- **Agency (Opt-out to Silence):** Users can explicitly toggle off "Native Distance" or "GPS Routes" in settings. Doing so **silences the warnings** and returns the system status to "EXCELLENT," giving the user full control over what is flagged.

#### 3. Reliability & Architectural Mapping
- **Inertia Backoff:** The background worker now uses an "Inertia" logic to avoid redundant cloud syncs unless significant activity (>500 steps) or a status change occurs.
- **Timezone Lock:** All system layers (Android, Spin, Python) are now strictly synchronized to `America/New_York` midnight for "Today" resets.
- **Architectural Docs:** Created `docs/MECRIS_ARCHITECTURE_DEEP_DIVE.md` to map the telemetry flow from sensor to Beeminder.

#### 4. Maintenance
- Fixed a `ServiceConnectionLeaked` bug in the OIDC layer.
- Cleaned up redundant `IntegrationsActivity` and consolidated UI components into the main source tree.
- Added the **Review Pump** velocity engine to the MCP server for daily language targets.

### 🚀 Verification Status
- [x] Timezone lock verified via Logcat.
- [x] Diagnostic detection of "NoData" for GPS routes confirmed.
- [x] Memory leak patch verified.
- [x] Back navigation gesture verified.

---
*This PR represents a significant step towards a transparent, diagnostic-rich nervous system for Mecris.*
