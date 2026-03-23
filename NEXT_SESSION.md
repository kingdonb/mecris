# Next Session: Failover Sync & Lever Validation

## Current Status (2026-03-23)
- **Rust Scraper (Spin)**: Fully enriched to extract `numPointsToday`, `tomorrow`, and `next_7_days`.
- **Beeminder Integration**: Rust service now pushes to Beeminder with an idempotency check (only if `numReadyForReview` changes).
- **Daily Completions**: Neon now stores `daily_completions` derived from `numPointsToday`, fixing the "0/184" nag issue.
- **Multiplier Lever**: Fixed the SQL query in the Rust service to handle the new `user_id` column in `language_stats`.
- **Schema**: Updated `mecris-go-spin/schema.sql` to include all language metrics.

## Verified
- [x] Bug: Failover sync not pushing to Beeminder.
- [x] Bug: Arabic Pressure nag stuck at 0.
- [x] Bug: Multiplier lever inconsistent (SQL fix applied).

## Pending Verification (Next Session)
- **Manual Trigger**: Verify that the Android app's "Failover Sync" results in a Beeminder datapoint with the correct comment.
- **Multiplier Sync**: Set the lever in the app and verify it persists in Neon (`SELECT pump_multiplier FROM language_stats`).
- **Coaching Persistence**: Ensure the Python MCP server reflects the changes made by the Rust service when it comes back online.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`. The Android worker is the primary trigger for failover sync when the MCP is dark.
- `language_stats` table now uses a composite primary key: `(user_id, language_name)`.
