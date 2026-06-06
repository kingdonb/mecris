# Local-First Development Workflow

This guide details the procedure for testing, verifying, and deploying the Mecris Spin and Android applications locally before releasing changes to the cloud. By following this local-first approach, we avoid "cowboy deployments" and ensure stable, verified releases.

## Core Concepts

The Mecris ecosystem spans several domains:
1. **The Android Client (mecris-go-project)**: Kotlin-based Jetpack Compose UI that fetches health data and coordinates syncs.
2. **The WASM Backend (mecris-go-spin/sync-service)**: A Rust-based Spin application deployed to Akamai/Fermyon that ingests Android data and proxies to third-party APIs (Beeminder, Twilio, Neon Postgres).
3. **The Data Layer**: A shared Serverless Postgres (Neon) instance storing goal statistics, budgets, and profile data.

## Setting Up the Local Spin Server

The Spin server relies heavily on environment variables for API keys and database connections. To test locally, we inject your .env variables into spin up.

1. **Ensure your .env is populated** at the project root.
2. **Run the local target**:
   make run-local
   
   This command will:
   - Compile the Rust WASM components (sync-service and review-pump).
   - Fetch the dynamic JWKS_JSON payload from your OIDC provider to allow local JWT validation.
   - Boot spin up listening on 0.0.0.0:3000 (allowing LAN traffic).

## Configuring the Android App for Local Testing

The Android application features a **Dynamic Backend Selector** to switch targets on the fly without recompiling the APK.

1. **Ensure the Android Emulator or Physical Device is on the same network** as your development machine.
2. **Build and install the APK**:
   cd mecris-go-project && ./gradlew app:assembleDebug
3. Open the **Profile Settings** screen (the person icon in the top right of the Dashboard).
4. Scroll to the bottom to find the **Backend Server** dropdown.
5. Select your target:
   - **Local (Emulator)**: Uses http://10.0.2.2:3000/. Select this if running the app in the Android Studio emulator on the same machine running spin up.
   - **Local (LAN: IP_ADDRESS)**: Uses your Mac's LAN IP (e.g., http://10.17.14.155:3000/). Select this if running the app on a physical Android device connected to Wi-Fi.
   - **Akamai/Fermyon Cloud**: The live production endpoints.
6. **Restart the app** fully for the networking configuration to take effect.

## Security Considerations for Local Testing

Android 9.0 and higher restrict cleartext (HTTP) network traffic by default. 

To allow the Android app to speak to your local spin server over HTTP:
- android:usesCleartextTraffic="true" is enabled in AndroidManifest.xml.
- The network_security_config.xml explicitly whitelists 10.0.2.2 and your specific LAN IP.
*(If your local IP address changes, you must update network_security_config.xml and rebuild the app).*

## Deployment

Once your changes are verified locally on both the Spin server and the Android client:

1. **Commit your changes.**
2. **Bump the version** (to ensure all components track the same release string):
   make bump-version VERSION=x.y.z [VC=nn]
3. **Deploy to both clouds**:
   make deploy-all
