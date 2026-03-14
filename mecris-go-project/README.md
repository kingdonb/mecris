# Mecris-Go Android App (Phase 1)

This directory contains the Phase 1 vertical slice for the Mecris-Go Android app. 

It implements the following core features:
1. **Pocket ID Authentication**: Integrates the Android `CredentialManager` API to support WebAuthn passkeys.
2. **Health Connect**: Requests permissions and polls the Health Connect SDK for Step and Distance records.
3. **Local Heuristics**: Applies an on-device rule (`Steps > 2000` & `Distance > 1000m`) to infer if a walk happened.
4. **WorkManager**: A background worker (`WalkHeuristicsWorker`) to poll Health Connect periodically.
5. **Beeminder Integration**: Direct-to-Beeminder POST requests using Retrofit, supporting idempotency keys.

## Getting Started

Because Android projects require complex Gradle wrapper environments and build files to compile correctly, these files are provided as the **core business logic and UI layer**. 

To build and run this app:
1. Open **Android Studio** (Flamingo or later).
2. Create a new "Empty Activity (Jetpack Compose)" project named `Mecris-Go`.
3. Set the package name to `com.mecris.go`.
4. Copy the contents of this `mecris-go/app` directory directly over the generated `app/` folder in Android Studio.
5. Update `MainActivity.kt` with your temporary Beeminder `YOUR_USERNAME` and `YOUR_AUTH_TOKEN`.
6. Sync Gradle and Run on a physical device.

*(Note: Health Connect requires a physical device or a modern emulator with the Health Connect app installed from the Play Store).*