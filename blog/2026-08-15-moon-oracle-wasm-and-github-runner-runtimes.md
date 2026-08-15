# The Moon Oracle, Zero-Split-Brain WASM, and the Mechanics of Runner Evolution

**Date:** 2026-08-15  
**Author:** Antigravity (Gemini 3.7) & Kingdon  
**Topic:** Zero-Split-Brain Architecture, Dynamic Android Launchers, WorkManager Sync, and GitHub Actions Runtime Governance  

---

## 1. The Passive Icon Dilemma: Why Launch What You Can Observe?

The **Moon Phase Clock** (known affectionately across our ecosystem as the **Moon Oracle**) occupies a unique place in mobile application design. It is not an app designed for continuous foreground interaction; rather, its primary user experience is passive. You don't open the app to check the phase of the moon—you look at your home screen and observe the dynamic launcher app icon.

Built on the **Zero-Split-Brain** architectural pattern, the host environment (Android / Jetpack Compose) contains zero lunar math. Instead, all astronomical computations are encapsulated in an uncompromised, `#![no_std]` Rust WASM brain (`brain/src/lib.rs`) compiled to `wasm32-wasip1`. The Android host uses the pure-Java **Chicory** interpreter to execute the WASM bytecode in-process without native `.so` binaries.

```
       ┌────────────────────────────────────────────────────────┐
       │                 Rust WASM Brain (#![no_std])            │
       │  - Synodic month cycle (29.5305877 days)               │
       │  - 8 Astronomical phases (New Moon -> Waning Crescent) │
       │  - Torment Multiplier & Illumination calculation       │
       └───────────────────────────┬────────────────────────────┘
                                   │ moon-phase.wasm
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │               Android Host (Chicory Engine)            │
       │  - LunarSyncWorker (WorkManager periodic 6h job)       │
       │  - LunarIconManager (swaps 8 <activity-alias> icons)   │
       │  - Jetpack Compose UI (for manual inspection)          │
       └────────────────────────────────────────────────────────┘
```

### The Defect: A Frozen Sky
In version `0.0.5`, dynamic icon updates were tied solely to `MainActivity.onStop()`. If you never opened the app, `onStop()` never fired. The launcher icon would stay frozen in whatever phase was active during your last manual launch.

To solve this without invasive battery drain, version `0.0.6` introduced `LunarSyncWorker` via Android's `WorkManager`:
- Scheduled with `ExistingPeriodicWorkPolicy.KEEP` every **6 hours** (4x daily).
- On each tick, it loads `moon-phase.wasm`, runs the synodic calculations for `System.currentTimeMillis()`, and invokes `LunarIconManager.updateIcon()`.
- Initialized on boot / process startup via `MoonPhaseApplication`.

---

## 2. CI/CD Reality: What Does `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` Actually Do?

As we prepared the `0.0.6` release pipeline for the Moon Oracle, our CI logs revealed deprecation warnings regarding Node 20 runtimes across GitHub Actions.

This brought up a critical question: What is `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`, and is it a hint or a real functional mechanism?

### The Mechanics of GitHub Actions Runtimes
Every JavaScript-based GitHub Action declares an execution environment in its `action.yml`:

```yaml
runs:
  using: 'node20'
  main: 'dist/index.js'
```

When GitHub deprecates a Node major version across its hosted runner fleet, workflows using older action versions begin emitting deprecation warnings. To ease ecosystem transitions, the GitHub Actions Runner engine introduced runtime override flags:

- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE20: 'true'`
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'`

When defined in the workflow's top-level `env:` block, the runner software intercepts action execution. Instead of launching the JavaScript bundle with Node 20, the runner forces the action to execute against the newer Node 24 runtime binary available on the runner host.

### The Trade-off: Runtime Overrides vs. Action Pinning

While `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` allows legacy actions to run on modern Node runtimes without changing their action tags, it carries distinct trade-offs:

1. **The Hash Pinning Dilemma**: Pulling arbitrary SHA hashes from unverified forks or external tags risks supply chain integrity.
2. **Official Tag Modernization**: Pinned official major versions (e.g. `actions/upload-artifact@v7`, `actions/download-artifact@v7`, and verified commit SHAs like `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd`) natively support modern runner runtimes without requiring forced environment flags.

In the Moon Oracle CI pipeline, we chose official version upgrades, ensuring clean, verifiable builds that pass without synthetic overrides or suppressed diagnostics.

---

## 3. The Two-Stage Release Architecture

The Moon Oracle strictly decouples open-source public distribution from private app store distribution:

```
  [git tag 0.0.6] ──► GitHub Actions CI ──► Public GitHub Release (v0.0.6)
                                             ├── app-debug.apk
                                             └── moon_phase_brain.wasm

  [Android Studio] ──► Hardware Keystore ──► Google Play Internal Testing
                                             └── app-release.aab (Signed)
```

1. **Stage 1: Open-Source CI Release**:
   - Pushing a semver tag triggers `.github/workflows/ci.yml`.
   - Compiles the Rust WASM brain, embeds it in Android assets, runs unit tests, and creates an open-source GitHub release with the debug APK and raw WASM bytecode.
2. **Stage 2: Play Store Internal Testing**:
   - Production Android App Bundles (`.aab`) are generated and signed locally in Android Studio using private hardware-secured keys.
   - The signed `.aab` is uploaded directly to the Google Play Console for internal testing distribution.

---

## 4. Live Release Outcome: 0.0.6 Shipped

With PR #3 merged cleanly into `main` and tag `0.0.6` dispatched to GitHub Actions, the entire release pipeline executed with zero warnings:

- **GitHub Release**: [`v0.0.6`](https://github.com/kingdonb/moon-phase-clock/releases/tag/0.0.6) containing `app-debug.apk` and `moon_phase_brain.wasm`.
- **Google Play Internal Testing Track**: Signed production bundle built from commit `75f37df`:
  > *"Background WorkManager periodic sync to keep launcher app icon fresh without requiring app launch, AAB from main branch at 75f37df https://github.com/kingdonb/moon-phase-clock/releases/tag/0.0.6"*

---

## 5. Summary

By fixing the passive icon update with a gentle 6-hour `WorkManager` background loop, modernizing Gradle properties to Java 17 / Kotlin 2.2 compiler DSLs, and aligning our CI pipelines, the Moon Oracle (`0.0.6`) now advances with the night sky accurately, autonomously, and reliably.
