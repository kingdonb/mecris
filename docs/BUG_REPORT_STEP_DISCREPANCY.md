# Bug Report: Step Discrepancy & Non-Deterministic Aggregation

## 1. The 1183 vs 2303 Discrepancy (Health Connect Over-counting)

**Status: RESOLVED**

**Implementation:**
The Android app now supports a `preferred_health_source` setting in `SharedPreferences` (`mecris_app_prefs`). When set, `HealthConnectManager` performs a specific `AggregateRequest` filtered by `DataOrigin` for that package name. This bypasses Health Connect's multi-source aggregation which was double-counting steps.

**How to set preferred source (Temporary workaround):**
Until the UI is built, the preferred source can be set via adb:
```bash
adb shell am broadcast -a com.mecris.go.SET_PREFERENCE --es key "preferred_health_source" --es value "com.google.android.apps.fitness"
```
*(Note: A broadcast receiver may need to be implemented to support this specific adb command, otherwise manual SharedPreferences editing is required).*

---

## 2. Non-Deterministic Database Read in Rust

**Status: RESOLVED**

**Implementation:**
The SQL query in `mecris-go-spin/sync-service/src/lib.rs` was updated to include an explicit `ORDER BY start_time ASC` clause. This ensures that the `.last()` operation in Rust reliably picks the most recent datapoint pushed by the Android app for the current day.

```sql
SELECT step_count FROM walk_inferences WHERE user_id = $1 AND start_time >= $2 ORDER BY start_time ASC
```