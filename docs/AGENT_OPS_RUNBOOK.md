# Agent Operations Runbook & Workarounds

This document records the operational quirks, workarounds, and nuances required for an AI agent to successfully interact with the Mecris environment, particularly during status updates, deployments, and debugging.

## 1. Authentication & Network Hangs (The VPN Issue)

**The Problem:**
If the user is disconnected from their VPN, OIDC token refreshes to `metnoom.urmanac.com` will fail because the host is unreachable. Previously, the `mecris login` CLI would hang indefinitely in a synchronous `requests.post` call, ignoring `Ctrl+C` because background threads blocked the Python interpreter from shutting down.

**The Fix / Workaround:**
1.  **Timeouts:** All `requests.post` calls in `services/auth_utils.py` must have explicit timeouts (`timeout=(3.0, 10.0)`).
2.  **Graceful Exits:** `cli/main.py` uses explicit `signal` handlers trapping `SIGINT` and `SIGTERM` to call `os._exit(130)` (a hard system exit), bypassing Python's thread-joining behavior.

**Operational Rule for Agents:**
When fetching status updates via CLI or MCP (`get_narrator_context`), if you encounter a timeout or hang, **do not attempt to fix the network**. Assume the user is off-VPN and wait for them to reconnect or use standalone fallbacks.

## 2. Health Connect Step & Distance Discrepancies

**The Problem:**
The Mecris Go Android app often reports different step counts and distances than native apps like Google Fit (e.g., Fit reports 1183 steps / 0.51 miles, while Mecris Go reports 2303 steps / 0.44 miles).

**The Explanation:**
Mecris Go uses Android's `HealthConnectClient.aggregate()` API. 
*   **Steps (`StepsRecord.COUNT_TOTAL`):** Health Connect automatically merges and deduplicates step data from *all* sources on the device (hardware pedometer, Google Fit, other wearables). If the hardware pedometer counted steps while the phone was in a pocket, but Fit wasn't tracking an explicit workout, the aggregate steps will be *higher* than Fit's isolated report.
*   **Distance (`DistanceRecord.DISTANCE_TOTAL`):** Distance is heavily reliant on GPS and stride-length estimates. Different apps use different algorithms. Health Connect's deduplication might prioritize a hardware sensor's shorter distance estimate over Google Fit's GPS-interpolated distance. 

**Operational Rule for Agents:**
When users ask about step/distance discrepancies, explain that Mecris relies on the **Health Connect Deduplicated Aggregate**, which is the "ground truth" intersection of all device sensors, not just one app's opinion. The discrepancy is a feature of the Android OS, not a bug in Mecris.

## 3. Autonomous Reminder Triggers (Spin Cloud)

**The Problem:**
Fermyon Spin Cloud does not support cron triggers. The newly built Rust WASM reminders (`/internal/trigger-reminders`) were initially orphaned.

**The Workaround:**
The Android app pushes step data to `/internal/cloud-sync`. The Rust backend has been modified so that *every successful cloud-sync automatically chains into a trigger-reminders evaluation*. 

**Operational Rule for Agents:**
To manually force an autonomous reminder check in the cloud, you must simulate an Android sync by sending an authenticated POST to the `/internal/cloud-sync` endpoint on the Spin Cloud URL.

## 4. Spin Cloud Variable Provisioning

**The Problem:**
Global settings (like Twilio keys and OpenWeather coordinates) must be manually provisioned in Spin Cloud because they are excluded from source control.

**The Workaround:**
Agents must use the explicit `spin cloud variables set` command (not `variable set`).
Example:
```bash
spin cloud variables set --app mecris-sync-v2 twilio_account_sid="AC123..."
```
*Note: Twilio auth tokens must be encrypted using `AES-256-GCM` with the `MASTER_ENCRYPTION_KEY` before being stored in Spin variables.*

## 5. MCP Server Operations & Auth Workarounds

**The Problem:**
In `MECRIS_MODE=multi-tenant`, the MCP server strictly requires a `user_id` for almost every tool call. If an agent calls a tool (like `get_narrator_context`) without an explicit ID, the server returns "Authentication Required," even if the user has successfully run `mecris login` on the local machine.

**The Workaround:**
Agents must explicitly provide the `user_id` in tool calls. 
1.  Locate the local user ID: `cat ~/.mecris/credentials.json | jq -r .user_id`.
2.  Pass it to the tool: `mcp_mecris_get_narrator_context(user_id="...")`.

**Process Restarts:**
If the server hangs or needs to pick up changes to local files (like `data/sms_consent.json`), it can be manually restarted by killing the process. **The Gemini CLI acts as the supervisor** and will automatically attempt to re-spawn the STDIO server upon the next tool call.
1.  Find the PID: `ps aux | grep mcp_server.py`
2.  Terminate it: `kill <PID>`
3.  The Gemini CLI will restart the server on the next turn, though there may be a brief "Not connected" error during the transition.

## 6. Multi-Tenancy Technical Debt (Updated)

**The Problem:**
The system is currently hardcoded to South Bend coordinates for weather, and SMS preferences are stored in a local `data/sms_consent.json` file. Additionally, the local `CredentialsManager` ignores stored credentials when the mode is set to `multi-tenant`, breaking the "default user" experience for local operators.

**Operational Rule for Agents:**
Until true database-backed multi-tenancy is built for these features, agents must manually manipulate `data/sms_consent.json` to toggle `vacation_mode` or adjust time windows. Weather coordinates must be manually updated via Spin Cloud variables if the user travels. If auth fails, use the `user_id` workaround in section 5.
