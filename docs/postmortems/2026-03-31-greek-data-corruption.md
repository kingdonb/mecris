# Post-Mortem: Greek Data Corruption (ellinika)

**Date**: 2026-03-31
**Duration**: Ongoing (discovered 17:45 UTC)
**Severity**: HIGH (Data corruption in Beeminder goal `ellinika`)
**Episode**: Mecris #160

## TL;DR
Automated syncs from both Python and Rust (Failover) were incorrectly pushing the Clozemaster Greek *review backlog count* (e.g., 23, 26) to the Beeminder goal `ellinika`. However, `ellinika` is an odometer/cumulative goal tracking total points (~26,000). This caused a massive drop in the Beeminder graph, triggering an unnecessary Beemergency.

## Timeline

| Time (UTC) | Event | Source |
|------------|-------|--------|
| 2026-03-28 | Bot "fixed" and pinned Greek slug to `ellinika` | session_log.md |
| 2026-03-29 | First reported "spurious" datapoint (value 23) | User Report |
| 2026-03-31 17:45 | Second reported drop (value 26) | User Report |
| 2026-03-31 18:00 | Investigation started | Gemini CLI |
| 2026-03-31 18:15 | Root cause identified in `lib.rs` and `clozemaster_scraper.py` | Gemini CLI |

## What Went Wrong

### Root Cause
The system assumed that every language tracked in Clozemaster should have a corresponding Beeminder goal where we push the `numReadyForReview` (backlog) count. While this is correct for Arabic (`reviewstack`), it is **incorrect** for Greek (`ellinika`), which tracks cumulative progress/points.

### Contributing Factors
- **Bot Over-Eagerness**: On 2026-03-28, the bot "pinned" the Greek slug to `ellinika` to resolve an ambiguity, without verifying if `ellinika` was a backlog-tracking goal.
- **Failover Sync (Rust)**: The Rust implementation duplicated the incorrect mapping from Python, ensuring that even if the Python server was down, the "Failover" would still corrupt the data.
- **Lack of Goal Type Validation**: The system does not check the Beeminder goal type (odometer vs. backlog) before pushing data.

## The Debugging Journey

### Attempt 1: Grep for "Failover"
**Hypothesis**: The log message "Auto-synced from Clozemaster (Failover)" must be in the codebase.
**Action**: `grep -r "Failover" .`
**Result**: Found in `mecris-go-spin/sync-service/src/lib.rs`.

### Attempt 2: Analyze Mappings
**Hypothesis**: The goal slug mapping is hardcoded.
**Action**: Inspected `lib.rs` and `scripts/clozemaster_scraper.py`.
**Result**: Both files have `"ell-eng" => "ellinika"` (Rust) or `"greek": "ellinika"` (Python).

## Recovery Steps (For Next Session)

1. **Delete Spurious Datapoints**: User has already manually deleted the 23 and 26 values.
2. **Modify Python Scraper**: In `scripts/clozemaster_scraper.py`, remove the Greek entry from the `languages` dictionary to stop Beeminder pushes, while keeping it in `LanguageSyncService` for database updates only.
3. **Modify Rust Scraper**: In `mecris-go-spin/sync-service/src/lib.rs`, change the mapping for `"ell-eng"` to return an empty Beeminder slug.
4. **Update Regression Tests**: Update `tests/test_greek_slug.py` to ensure it prevents *pushing* to `ellinika`, rather than *pinning* it as a push target.

## Failure Pattern Analysis
**Pattern Category**: [RECURRENCE] - This happened before on 2026-03-29.
**Pattern ID**: PM-CM-001 (Clozemaster Backlog/Odometer Mismatch)

## Prevention & Detection

### Immediate Actions (Next Session)
- [ ] Fix `scripts/clozemaster_scraper.py`: Owner: `mecris-bot`
- [ ] Fix `mecris-go-spin/sync-service/src/lib.rs`: Owner: `mecris-bot`
- [ ] Update `tests/test_greek_slug.py` to catch "unexpected push" errors.

### Long-term Improvements
- Implement a `goal_type` check in `BeeminderClient` to prevent pushing "snapshots" to "odometers".
- Add a "Blacklist" of goals that should never be automated.

## The Honest Assessment

### What We Did Well
- Identified the duplicate logic in Rust and Python quickly.
- Traced the "Failover" message to the specific source line.

### What We Could Have Done Better
- The bot should have questioned the "Number Go Up" nature of `ellinika` before pinning it. 
- "Friction is a Feature": The bot found it too easy to just map Greek to `ellinika` without checking the units.

## Recovery Playbook

```bash
# To verify the fix in Python:
PYTHONPATH=. python -m scripts.clozemaster_scraper --dry-run | grep -i "greek"
# Should show scraping data but NOT "Would push ... to ellinika"

# To verify the fix in Rust:
cd mecris-go-spin/sync-service && cargo test
# (Assuming unit tests are added for the mapping logic)
```
