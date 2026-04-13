# Bug Report: Step Discrepancy & Non-Deterministic Aggregation

## 1. The 1183 vs 2303 Discrepancy (Health Connect Over-counting)

**Observation:**
The user observed Google Fit reporting 1,183 steps (0.51 miles), while Mecris Go synced 2,303 steps (0.44 miles / 705 meters) to the database.

**Root Cause Analysis:**
The Android app relies on `HealthConnectClient.aggregate()` requesting `StepsRecord.COUNT_TOTAL` from `startOfToday` to `now`. 
While Health Connect attempts to deduplicate steps, it often fails if multiple apps (e.g., Google Fit, a hardware pedometer service, Samsung Health) write step records with slightly misaligned timestamps or intervals. When deduplication fails, the aggregate sum effectively double-counts the steps (1183 * 2 ≈ 2366, which is remarkably close to the 2303 reported). 

**Why the distance is lower:**
Distance (`DistanceRecord.DISTANCE_TOTAL`) is derived differently. It appears Health Connect *did* successfully deduplicate or prioritize one source for distance (likely the hardware pedometer's internal math: 705 meters = 0.44 miles), discarding Google Fit's GPS-based 0.51 miles.

**Proposed Fix for Android:**
Instead of relying on the raw `aggregate()` API for steps, the Android app should query `StepsRecord` specifically filtering for the user's preferred source (e.g., explicitly trusting `com.google.android.apps.fitness`) to bypass Health Connect's flawed multi-source deduplication.

---

## 2. Non-Deterministic Database Read in Rust

**Observation:**
While investigating the above, a critical flaw was discovered in the Rust WASM backend (`mecris-go-spin/sync-service/src/lib.rs`).

**Root Cause Analysis:**
The `aggregate_step_count` function was correctly updated to use `.last()` to align with Beeminder's `AggDay=last` paradigm. However, the SQL query feeding it does not enforce an order:
```sql
SELECT step_count FROM walk_inferences WHERE user_id = $1 AND start_time >= $2
```
Because Postgres does not guarantee row order without an explicit `ORDER BY` clause, `.last()` may randomly select the *oldest* step count of the day (or even a previous day if timezone overlaps occur) depending on how the rows are physically stored on disk.

**Proposed Fix for Rust:**
The query must be updated to enforce chronological ordering:
```sql
SELECT step_count FROM walk_inferences WHERE user_id = $1 AND start_time >= $2 ORDER BY start_time ASC
```
*(Alternatively `DESC LIMIT 1` directly in SQL).*