# Implementation Plan: Human-Centric Notification Engine

## Technical Stack
- **Backend**: Rust (Spin API), Neon Postgres.
- **Mobile**: Kotlin (Android), WorkManager, Health Connect, Jetpack Compose.

## Architecture Decisions
- **Two-Stage Worker**: 
    - `WalkHeuristicsWorker` acts as the detector. It calculates a random delay using `java.util.Random` and schedules `DelayedNagWorker` using `OneTimeWorkRequestBuilder`.
    - `DelayedNagWorker` uses `inputData` to know what the original target was, but always re-queries `SyncServiceApi` or local state before notifying.
- **Narrative Oracle (Backend)**:
    - New Rust endpoint `/narrator/weather-heuristic` in `sync-service`.
    - It consumes `lat`, `lon` and returns detailed weather + solar status.
    - Uses `openweather_api_key` from Spin variables.
- **Privacy First Location**:
    - Coordinates are stored in the `users` table via `location_lat` and `location_lon`.
    - Android app only sends these if the user has opted in.
    - "View on Maps" intent uses `geo:lat,lon?q=lat,lon(Stored+Location)`.
- **Package Intents**:
    - `context.packageManager.getLaunchIntentForPackage("com.clozemaster.v2")` for language goals.
    - `context.packageManager.getLaunchIntentForPackage("com.google.android.apps.healthdata")` for physical goals.

## Database Schema Changes
- `ALTER TABLE users ADD COLUMN vacation_mode_until TIMESTAMPTZ;`
- (Already existing) `location_lat`, `location_lon` from migration 004.

## Milestones
1. **Milestone 1: Backend Narrative Layer**
    - Implement `/narrator/weather-heuristic`.
    - Add `vacation_mode_until` to `users` table and API response.
2. **Milestone 2: Android Two-Stage Worker**
    - Implement `DelayedNagWorker`.
    - Update `WalkHeuristicsWorker` to schedule delayed work.
    - Implement "Pivot" logic in `DelayedNagWorker`.
3. **Milestone 3: UI & Action Integration**
    - Build Profile/Settings UI for Location and Vacation Mode.
    - Add action buttons to notifications for deep-linking.

## Dependencies
- **OpenWeather API Key**: Must be configured in Spin.
- **Neon DB**: Access required for migration and API.
- **Health Connect Permissions**: Handled by existing `HealthConnectManager`.
