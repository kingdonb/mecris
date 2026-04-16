-- Migration 005: Add autonomous sync consent and debouncing fields
--
-- Context: yebyen/mecris#185
-- Adds a consent flag for background tasks (cron) and a timestamp for debouncing.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS autonomous_sync_enabled BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS last_autonomous_sync TIMESTAMPTZ;

COMMENT ON COLUMN users.autonomous_sync_enabled IS 'Consent flag to allow automated tasks (like failover-sync) to run on behalf of the user.';
COMMENT ON COLUMN users.last_autonomous_sync IS 'Timestamp of the last autonomous sync, used for debouncing to protect compute resources.';
