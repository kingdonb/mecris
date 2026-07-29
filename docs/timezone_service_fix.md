# TimezoneService Extraction — Priority 1 Fix

## Problem Statement

Two silent data corruption bugs caused by scattered, inconsistent timezone handling:

| Bug | Location | Symptom |
|-----|----------|---------|
| **#1** | `neon_sync_checker.py:102-103` | `has_walk_today()` compares Eastern-wall-time SQL result against naive parameter → walks misclassified at midnight boundaries (±4-5hr) |
| **#2** | `mcp_server.py:1115-1125` | Groq reading daystamp assumes naive datetime = UTC, but tracker stores local (Eastern) → datapoints sent to wrong Beeminder day |

Root cause: No canonical timezone abstraction. `zoneinfo.ZoneInfo("US/Eastern")` instantiated in 5+ files, `astimezone()`/`replace(tzinfo=...)` used inconsistently.

---

## Solution: Single-Purpose TimezoneService Module

Create `services/timezone_service.py` with **only** these 4 pure functions:

```python
# services/timezone_service.py
from datetime import datetime, date
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

def today_eastern() -> date:
    """Current date in US/Eastern (for daily boundaries)."""
    return datetime.now(EASTERN).date()

def daystamp(dt: datetime) -> str:
    """YYYYMMDD string for Beeminder requestid / daystamp."""
    return dt.astimezone(EASTERN).strftime("%Y%m%d")

def day_start_eastern(d: date) -> datetime:
    """00:00:00 Eastern on given date (aware)."""
    return datetime.combine(d, datetime.min.time(), tzinfo=EASTERN)

def to_eastern(dt: datetime) -> datetime:
    """Normalize any datetime to Eastern (aware). Naive treated as Eastern."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=EASTERN)
    return dt.astimezone(EASTERN)
```

**No other functions. No classes. No I/O. No config.**

---

## Files to Modify

### 1. `services/neon_sync_checker.py` (fixes Bug #1)
```python
# BEFORE (lines 102-103):
today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
params = [today_start.replace(tzinfo=None), min_steps]

# AFTER:
from services.timezone_service import day_start_eastern
today_start = day_start_eastern(local_now.date())
params = [today_start, min_steps]  # aware datetime, no tzinfo stripping
```

SQL query unchanged: `start_time::TIMESTAMPTZ AT TIME ZONE 'America/New_York'` returns Eastern-wall-time; aware parameter matches correctly.

### 2. `mcp_server.py` Groq handler (fixes Bug #2)
```python
# BEFORE (lines 1115-1125):
record_dt = datetime.fromisoformat(ts_str)
if record_dt.tzinfo is None:
    record_dt = record_dt.replace(tzinfo=timezone.utc)  # WRONG assumption
daystamp = record_dt.astimezone(eastern).strftime("%Y%m%d")

# AFTER:
from services.timezone_service import daystamp, to_eastern
record_dt = to_eastern(datetime.fromisoformat(ts_str))
daystamp = daystamp(record_dt)
```

`groq_odometer_tracker` stores `datetime.now()` (naive local/Eastern). `to_eastern()` treats naive as Eastern → correct daystamp.

### 3. `services/language_sync_service.py` (consistency)
Replace inline `zoneinfo.ZoneInfo("US/Eastern")` with `today_eastern()` / `day_start_eastern()`.

### 4. `scripts/clozemaster_scraper.py` (consistency)
Same — uses Eastern for Beeminder daystamp alignment.

---

## Android Mirror (Future, Not This PR)

Kotlin port `TimezoneService.kt` with identical 4 functions using `ZoneId.of("America/New_York")`. Used by:
- `WalkHeuristicsWorker` (day boundaries)
- `ReviewPumpCalculator` (if it ever needs daystamp)

**Not included in this fix** — Python-only first. Android can adopt later.

---

## Testing

Unit tests in `tests/test_timezone_service.py`:
```python
def test_today_eastern_matches_system():
    assert today_eastern() == datetime.now(ZoneInfo("America/New_York")).date()

def test_daystamp_naive_treated_as_eastern():
    dt = datetime(2026, 7, 30, 23, 0)  # naive, 11pm Eastern
    assert daystamp(dt) == "20260730"

def test_daystamp_utc_converted():
    dt = datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc)  # 11pm Eastern previous day
    assert daystamp(dt) == "20260730"

def test_day_start_eastern_aware():
    d = date(2026, 7, 30)
    dt = day_start_eastern(d)
    assert dt.tzinfo == EASTERN
    assert dt.hour == 0 and dt.minute == 0
```

Property test: `daystamp(to_eastern(dt)) == daystamp(dt.astimezone(EASTERN))` for random aware/naive datetimes.

---

## Rollback Plan

Single commit. Revert = delete `services/timezone_service.py` + restore 4 call sites to inline `zoneinfo` usage. No DB changes, no schema migrations, no config.

---

## Out of Scope (Explicitly)

- ❌ Coordinator process separation
- ❌ Spin webhook unification
- ❌ ReviewPump shared library (Priority 2)
- ❌ Walk cache pg_notify trigger (Priority 3)
- ❌ Android Kotlin port
- ❌ Any architecture changes

---

## Acceptance Criteria

1. `has_walk_today()` returns correct result at midnight Eastern boundaries
2. Groq datapoints appear on correct Beeminder day (verified by manual entry)
3. All 4 call sites use `TimezoneService` (grep confirms no inline `ZoneInfo("US/Eastern")` in modified files)
4. Unit tests pass
5. No regression in existing narrator/daily aggregate status