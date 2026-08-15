---
name: chore-moon-clock-inventory
description: 'Weekend chore 5-minute survey and verification for Moon Oracle (Moon Phase Clock), zero-split-brain WASM lunar brain, dynamic app icon swapping, and WorkManager background updates. Trigger with /chore-moon-clock-inventory'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Weekend Chore: Moon Oracle (Moon Phase Clock) Inventory

Part of the **Weekend Chores** accountability workflow. This skill guides the **human operator** and AI assistant through a 5-minute inspection of the **Moon Oracle** (`tools/moon-phase-clock`), its Zero-Split-Brain WASM calculation engine, Jetpack Compose Android client, and dynamic app-icon swapping system.

## The Moon Oracle Architecture

The Moon Oracle is a mathematically precise lunar awareness system built on the **Zero-Split-Brain** philosophy:
- **The Brain (`tools/moon-phase-clock/brain/src/lib.rs`)**: A pure, `#![no_std]` Rust WASM module compiled to `wasm32-wasip1`. It calculates synodic cycle position, phase names (8 phases), torment multipliers, and illumination without host-side discrepancies.
- **The Host Engine (`WasmEngine.kt`)**: Uses Chicory (pure Java WASM interpreter) inside Android to execute `moon-phase.wasm` without native JNI `.so` binaries.
- **The Dynamic App Icon (`LunarIconManager.kt` & `AndroidManifest.xml`)**:
  - Employs 8 `<activity-alias>` launcher entry points (`MainActivityDefault`, `MainActivityWaxingCrescent`, `MainActivityFirstQuarter`, `MainActivityWaxingGibbous`, `MainActivityFull`, `MainActivityWaningGibbous`, `MainActivityLastQuarter`, `MainActivityWaningCrescent`).
  - Swaps launcher components via Android `PackageManager.setComponentEnabledSetting()`.
- **Background Periodic Sync (`WorkManager` / `PeriodicWorkRequest`)**:
  - Periodically executes the WASM brain every 4–6 hours (e.g. 4x–6x daily) to advance the home screen app icon even when the app is never manually foregrounded.

---

## 5-Minute Guided Chore Routine

### Step 1: Verify the WASM Brain
```bash
cd tools/moon-phase-clock/brain
cargo build --target wasm32-wasip1 --release
```
- Confirms the Rust WASM engine compiles cleanly and validates the synodic cycle constants (`KNOWN_NEW_MOON_UNIX = 947182440.0`, `SYNODIC_MONTH_DAYS = 29.53058770576`).

### Step 2: Verify Android Test Suite & Asset Sync
```bash
cd tools/moon-phase-clock
export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$PATH"
./gradlew test
```
- Ensures Chicory runtime, Compose BOM, and unit test suites pass.

### Step 3: Inspect Dynamic Launcher Icon Aliases
```bash
# View current activity-aliases and launcher configuration
view_file tools/moon-phase-clock/android/app/src/main/AndroidManifest.xml
```

### Step 4: Human Visual Confirmation (The Chore)
1. Check your Android device's home screen or app drawer for the **Moon Oracle** icon.
2. Confirm the icon visual matches the current lunar phase in the night sky (or astronomical almanac).
3. If the phase icon is lagging, verify background WorkManager execution or launch the app to trigger immediate synchronization.
