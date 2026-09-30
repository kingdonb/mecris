---
name: mecris-edge-sync-e2e
description: End-to-end sync verification and diagnostics runbook between the Android app (com.mecris.go), Spin/Akamai edge services, and Neon Postgres (e.g. Helix balance sync, Beeminder, Clozemaster). Use when deploying edge updates, forcing Android refreshes via ADB, inspecting database witness tables, or troubleshooting outbound edge permissions (ErrorCode::HttpRequestDenied) and Android background execution blocks.
---

# Mecris Edge Sync & E2E Diagnostics Skill

This skill documents the complete procedure for deploying, triggering, and verifying end-to-end data flows between the **Android Client (`com.mecris.go`)**, the **Spin Edge Services (Akamai Functions)**, and the **Neon Postgres Database**.

---

## 1. Quick Reference Commands

| Stage | Command / Script | Purpose |
| :--- | :--- | :--- |
| **Verify Branch** | `git log --oneline -n 3` | Ensure required fixes/manifests are present locally |
| **Run Migrations** | `python scripts/migrate_<name>.py` | Apply any pending Neon DB schema additions |
| **Deploy Edge** | `make deploy-akamai` | Build WASM components & push app to Akamai Functions |
| **Force App Sync** | `bash .agents/skills/mecris-edge-sync-e2e/scripts/trigger_refresh.sh` | Cold-start app via ADB to bypass 5-min cache |
| **Check Witnesses** | `python .agents/skills/mecris-edge-sync-e2e/scripts/check_witnesses.py` | Query Neon DB for fresh requests, logs, and errors |

---

## 2. Architecture & The Verification Chain

Data flow follows an **Edge-Primary** model with the Android app acting as an agnostic doorbell:

```
[ Android App ] --(POST /<feature>/request with OIDC token)--> [ Akamai Edge (Spin) ]
        |                                                              |
        | (Bypasses 5m cache on cold start)                            |-- 1. Writes request to Neon
        | (Also fires on 15m WorkManager heartbeat)                    |-- 2. Fetches upstream API (Helix/Beeminder)
        v                                                              |-- 3. Writes log & updates processed_at
[ Neon DB (Witnesses) ] <----------------------------------------------+
```

### The Three Witnesses
Whenever verifying that an E2E sync succeeded:
1. **Fresh `requested_at`**: The request queue row (e.g., in `helix_balance_requests`) shows a timestamp matching the trigger.
2. **Execution Row**: The log table (e.g., `helix_balance_log`) contains a corresponding row with `fetch_status = 'ok'` and expected payload.
3. **Upstream Reflection**: Upstream service (e.g. Beeminder goal `helix-ml`, Clozemaster) reflects the new value.

---

## 3. Diagnostic Procedures

### A. Outbound HTTP Denied (`ErrorCode::HttpRequestDenied`)
- **Cause**: Spin wasi-http runtime enforces an outbound host allowlist in `spin.toml`. If a component calls an undeclared host, the runtime throws `ErrorCode::HttpRequestDenied`.
- **Location**: `mecris-go-spin/sync-service/spin.toml` under `[component.sync-service]`.
- **Fix**:
  Ensure the host is in `allowed_outbound_hosts`:
  ```toml
  allowed_outbound_hosts = [
      "postgres://*:*",
      "https://www.beeminder.com",
      "https://app.helix.ml"
  ]
  ```
- **Deployment**: Manifest changes are compiled into the deployment package at deploy time. Run `make deploy-akamai` after modifying `spin.toml`.

### B. Android Per-UID Network / Background Restrictions
- **Symptom**: App (UID `10516` or similar) cannot make TCP connections or sync while backgrounded or on specific subnets (e.g. `13-net`), while shell user (`UID 2000`) connects fine.
- **Check Block State**:
  ```bash
  adb shell dumpsys netpolicy | grep -A 2 "UID=10516"
  ```
  Look for `blocked_state={...,effective=APP_BACKGROUND}`.
- **Remediation**:
  Exempt app from power/idle restrictions:
  ```bash
  adb shell dumpsys deviceidle whitelist +com.mecris.go
  ```
  Verify permission in `AndroidManifest.xml`:
  ```xml
  <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
  ```

### C. Triggering Android Cold-Start via ADB
To bypass the in-memory 5-minute cache (`isCacheStale(5)`) without wiping auth tokens or data:
```bash
adb shell input keyevent KEYCODE_WAKEUP
adb shell am force-stop com.mecris.go
adb shell monkey -p com.mecris.go -c android.intent.category.LAUNCHER 1
```

---

## 4. Helper Scripts

- **`trigger_refresh.sh`**: Wakes the phone screen, unlocks keyguard, force-stops the app, and relaunches the main activity.
- **`check_witnesses.py`**: Reads `.env`, connects to `NEON_DB_URL`, and prints the latest 3 entries from both request and execution log tables.
