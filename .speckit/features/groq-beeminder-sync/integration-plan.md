# Integration Plan: Groq-Beeminder Trip Odometer Sync

## 🏗️ Architecture Summary
The integration connects the existing `GroqOdometerTracker` (which records data in Neon) with the `BeeminderClient` (which pushes datapoints to Beeminder). The sync logic will be invoked directly from the `record_groq_reading` MCP tool in `mcp_server.py` or within the tracker itself.

## 🔄 Interaction Flow
1. User invokes the `record_groq_reading` MCP tool.
2. `GroqOdometerTracker.record_odometer_reading` is called to save the reading to the Neon database.
3. The tracker returns a result dictionary, including whether a `reset_detected` event occurred.
4. **New Integration Step:** A new function `sync_groq_to_beeminder(reading_data, target_user_id)` is called.
5. If `reset_detected` is true (indicating a month boundary), the sync function pushes a `@TARE` datapoint (`value: 0`) for the appropriate date.
6. The sync function then pushes the actual recorded reading (`value: reading_data['cumulative_value']`).

## 🧱 Component Modifications

### 1. `mcp_server.py`
- **Modify:** `record_groq_reading` tool.
- **Action:** Import the `BeeminderClient` and handle the push to Beeminder *after* the local tracker successfully records the data. We will wrap this in a `try/except` to ensure the local DB write is the primary source of truth, and a Beeminder API failure doesn't crash the MCP tool.

### 2. `beeminder_client.py`
- **Verify/Add:** Ensure `BeeminderClient` has a robust method to post datapoints with a specific `daystamp` and `comment`. (It likely already has a `post_datapoint` method).

### 3. Date & Timezone Handling
- **Hardcode Start Date:** As agreed, we will hardcode the goal start date (`2026-04-13`) to prevent syncing data prior to the goal's existence.
- **Timezone:** Ensure the `daystamp` is formatted in the user's local timezone (US/Eastern by default in this system) to align with Beeminder's daily deadlines.

## ⚠️ Risk Mitigation
- **Out-of-Order Syncs:** Handled natively by Beeminder. The system will blindly push the datapoints for the dates requested. If a user records today's data, then yesterday's data, the system will push them in that order. Beeminder will sort them by `daystamp`.
- **API Errors:** The Beeminder push will fail gracefully (logging the error) without rolling back the successful Neon database write.

## 🧪 Testing Strategy
- Unit tests mocking the `BeeminderClient` to ensure `record_groq_reading` calls the post method with the correct parameters (including the `@TARE` logic).
