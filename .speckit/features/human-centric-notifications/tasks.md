# Tasks: Human-Centric Notification Engine

## Milestone 1: Backend Narrative Layer
- [x] **Task 1.1**: Create migration `006_vacation_mode.sql` for `vacation_mode_until`.
- [x] **Task 1.2**: Implement `/narrator/weather-heuristic` in `mecris-go-spin/sync-service/src/lib.rs`.
- [x] **Task 1.3**: Update `AggregateStatusResponseDto` to include `vacation_mode_until`.
- [x] **Task 1.4**: Add unit tests for `weather-heuristic` in Rust.

## Milestone 2: Android Two-Stage Worker
- [x] **Task 2.1**: Create `DelayedNagWorker.kt` in `com.mecris.go.health`.
- [x] **Task 2.2**: Update `WalkHeuristicsWorker.kt` to calculate random delay and schedule `DelayedNagWorker`.
- [x] **Task 2.3**: Implement "Pivot" logic in `DelayedNagWorker` (re-fetch status and select next priority).
- [x] **Task 2.4**: Add solar suppression logic to `DelayedNagWorker` (using `/internal/weather-heuristic`).

## Milestone 3: UI & Action Integration
- [x] **Task 3.1**: Enhance `ProfileSettingsScreen.kt` with Vacation Mode picker.
- [x] **Task 3.2**: Add "View on Maps" button and location clearing logic to UI.
- [x] **Task 3.3**: Add action buttons to `NagNotificationManager.kt` using `NotificationCompat.Action`.
- [x] **Task 3.4**: Implement `Logout` button and `PocketIdAuth` clear logic.

## Milestone 4: Verification & Hardening
- [ ] **Task 4.1**: E2E test of the "Fuzzy Pivot" (Goal A -> Wait -> Goal B).
- [ ] **Task 4.2**: Verify solar suppression on a live device.
