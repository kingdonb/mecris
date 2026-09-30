#!/usr/bin/env bash
# Trigger a cold start of com.mecris.go on connected Android device
set -euo pipefail

ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
if ! command -v "$ADB" >/dev/null 2>&1; then
    if command -v adb >/dev/null 2>&1; then
        ADB="adb"
    else
        echo "Error: adb not found at $ADB and not in PATH" >&2
        exit 1
    fi
fi

echo "Waking device and bringing com.mecris.go to foreground..."
"$ADB" shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true
"$ADB" shell input keyevent 82 2>/dev/null || true
"$ADB" shell am force-stop com.mecris.go
"$ADB" shell monkey -p com.mecris.go -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1

echo "App cold-started. Waiting 5s for network requests to dispatch..."
sleep 5
echo "Done."
