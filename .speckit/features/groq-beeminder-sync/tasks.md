# Task Breakdown: Groq-Beeminder Trip Odometer Sync

## 📋 Task List

### Phase 1: Core Logic Implementation
- [x] **Task 1: Extend `BeeminderClient`**
  - [x] Verify if `BeeminderClient` in `beeminder_client.py` has a method to post datapoints with a specific `daystamp` and `comment`.
  - [x] If not, add `add_datapoint(self, goal_slug: str, value: float, comment: str = "", daystamp: str = None) -> bool`.
- [x] **Task 2: Implement Sync Logic in `mcp_server.py`**
  - [x] Locate the `record_groq_reading` MCP tool definition.
  - [x] Import `get_user_beeminder_client` or instantiate the client directly.
  - [x] After calling the local `record_groq` tracker, check the returned dictionary for `reset_detected`.
  - [x] Add logic to conditionally send the `@TARE` datapoint if a reset occurred.
  - [x] Add logic to unconditionally send the actual reading value.

### Phase 2: Date & Timezone Handling
- [x] **Task 3: Goal Start Date Restriction**
  - [x] Hardcode the start date (`2026-04-13`) as a constant (e.g., `GROQSPEND_START_DATE`).
  - [x] Add a check before syncing: If the reading's target date is *before* the start date, skip the Beeminder API call and log a message.
- [x] **Task 4: Formatting the `daystamp`**
  - [x] Ensure the date being passed to the `BeeminderClient` is formatted as `YYYYMMDD`.
  - [x] Use the `US/Eastern` timezone for any `datetime.now()` calls to match the user's expected Beeminder deadline.

### Phase 3: Testing & Validation
- [x] **Task 5: Unit Tests for Sync Logic**
  - [x] Create or update tests in `tests/test_mcp_server.py` (or a dedicated test file).
  - [x] Mock the `BeeminderClient` to verify that `add_datapoint` is called with the correct `value`, `comment` (including `@TARE`), and `daystamp`.
  - [x] Ensure the local Neon DB recording still succeeds even if the Beeminder mock is set to raise an exception.
