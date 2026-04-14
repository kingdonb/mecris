# Specification: Groq-Beeminder Trip Odometer Sync

## 🎯 Objective
Enable seamless synchronization of manual Groq odometer readings from the local Neon database to the Beeminder `groqspend` goal, using Beeminder's `@TARE` feature to handle the monthly "Trip Odometer" reset.

## 👤 User Stories
- **As a user**, I want my manual Groq cost updates to automatically reflect on my Beeminder graph.
- **As a user**, I want the system to handle the monthly "reset to zero" at Groq by sending a `@TARE` datapoint, so my lifetime spend is tracked continuously.
- **As a user**, I want to be able to record historical data points (after the goal's start date), relying on Beeminder's date-awareness to place them correctly on the graph.

## ✅ Functional Requirements

### FR-001: Automatic Sync on Record
When a new reading is recorded via the `record_groq_reading` MCP tool, the system MUST push this value as a datapoint to the Beeminder `groqspend` goal. The datapoint must use the correct `daystamp` matching the date of the record.

### FR-002: Trip Odometer Reset (@TARE)
If the `record_odometer_reading` logic detects a reset (i.e., `reset_detected` is True, typically at month boundaries), the system MUST:
1. Send a datapoint to Beeminder for the reset date with `value: 0` and `comment: "@TARE [Month] Reset"`.
2. Send the actual recorded value as a subsequent datapoint.

### FR-003: Historical Data Support
The system MUST permit the synchronization of historical readings. Because Beeminder is date-aware, out-of-order syncing (e.g., recording today's tare, then yesterday's data) is fully supported natively by Beeminder. The system will NOT restrict historical sync, provided the date is not before the Beeminder goal's creation date.

## 📐 Success Criteria
- **SC-001:** Recording a value of `$0.05` for the current month results in a Beeminder datapoint of `0.05` with today's `daystamp`.
- **SC-002:** Recording the first value of a new month that triggers a reset results in TWO Beeminder datapoints being sent:
    1. A `@TARE` datapoint (`value: 0`).
    2. The actual reading datapoint.
- **SC-003:** Recording a historical value sends a datapoint with the corresponding historical `daystamp`.

## 🧪 Edge Cases
- **EC-001: Pre-Goal Historical Data:** If a user attempts to record historical data from *before* the `groqspend` goal was created, the system should ideally reject the sync to avoid API errors from Beeminder, or simply log the Beeminder rejection gracefully.
