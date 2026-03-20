# Next Session Plan - 2026-03-20

## 🎯 Primary Goal: Autonomous High Availability
Finalize the transition of Mecris into a resilient, cross-runtime system that survives local server downtime.

## 📋 Tasks

### 1. 🤖 Implement native Spin Cron (Issue #100)
- Add `[[trigger.cron]]` to `mecris-go-spin/sync-service/spin.toml`.
- Configure it to run every 2 hours (or daily at 8 AM).
- Refactor the Rust code to share the `run_clozemaster_scraper` logic between the HTTP and Cron components.
- **Why**: This removes the need for external ping services and ensures the cloud keeps goals safe even if the laptop is closed.

### 2. 📱 Android UI Urgency (Issue #92)
- Update the Android App's language view to use the new `safebuf` and `derail_risk` fields.
- Implement color-coding (Red for Critical, Yellow for Warning).
- Add a "System Status" indicator to show if the Leader is Home (Python) or Cloud (Failover).

### 3. 🗣️ Voice Commands Thinger (Option C)
- Revisit the background process for asynchronous voice command processing.
- Define the ingestion path (Twilio Audio -> Whisper -> Mecris Command).

### 4. 🧹 Tech Debt: `message_log` cleanup
- Now that we confirmed `message_log` is in Neon, ensure the MCP server's `send_reminder_message` uses it *first* and only falls back to SQLite if Neon is unreachable (currently it catches exceptions and falls back, but doesn't proactively check).

## 🧪 Testing Focus
- Continue using TDG for all new logic.
- Target the Rust Spin backend with unit tests (using `mockall` or similar if needed).
- Verify the Failover Mode by stopping the local MCP server and ensuring the Spin backend takes over.

**Mecris Note**: The "Infinite Postponement" bug was a major hurdle cleared today. Tomorrow we build on that stability.
