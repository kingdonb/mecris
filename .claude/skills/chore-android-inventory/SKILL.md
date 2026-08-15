---
name: chore-android-inventory
description: 'Weekend chore 5-minute guided walkthrough for the Mecris Android app (Kotlin, Compose, Health Connect, WorkManager, PocketID OIDC, and Live ADB log inspection). Trigger with /chore-android-inventory'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Weekend Chore: Android App Guided Walkthrough & Diagnostics

Part of the **Weekend Chores** accountability workflow. This skill guides the **human operator** and AI assistant together through a 5-minute check of the Mecris Android client.

## The Weekend Chores Philosophy: Human-in-the-Loop

- **Role of the Agent**: Copilot and diagnostic inspector (running ADB checks, reviewing logs, checking WorkManager status).
- **Role of the Human**: The human opens the Android client, checks step counts, triggers a sync if needed, and verifies real-time telemetry.

---

## 5-Minute Guided Chore Routine

### Step 1: Open the App on Your Phone
1. Launch **Mecris Go** on your Android device.
2. Confirm the dashboard loads and displays today's distance / step count.
3. Check the cloud sync indicator.

### Step 2: Live Diagnostic Check (Copilot Pass)
```bash
export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$HOME/Library/Android/sdk/platform-tools:$PATH"
adb devices
adb logcat -d -v time | grep -E "MecrisDashboard|HealthConnectManager|WalkSyncWorker" | tail -n 30
```
- **Verify**: Health Connect sessions found in the last 30d and recent surgical refresh timestamps.

### Step 3: Test Build Baseline
```bash
export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$HOME/Library/Android/sdk/platform-tools:$PATH"
cd /Users/yebyen/w/mecris/mecris-go-project
./gradlew testDebugUnitTest
```

---

## Diagnostic Notes

- **Perimeter Requirement**: PocketID token refresh requires connection to the home LAN or VPN. If you are away from home without VPN, Health Connect continues recording steps locally, but cloud sync waits until check-in.
- **Language Momentum / Greek Pipe**: When the Greek review pipe thins (future reviews low), play new Greek cards in Clozemaster to maintain forward momentum.
