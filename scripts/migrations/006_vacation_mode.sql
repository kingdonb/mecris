-- Migration 006: Add vacation mode sensitivity override
--
-- Context: yebyen/mecris#188 (Human-Centric Notifications)
-- Adds a timestamp to allow the narrative to suppress doggie-specific
-- references during sensitive periods. NULL = Normal Mode; TIMESTAMP = Sensitive Mode.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS vacation_mode_until TIMESTAMPTZ;

COMMENT ON COLUMN users.vacation_mode_until IS 'Sensitivity override timestamp. If CURRENT_TIMESTAMP < vacation_mode_until, doggie-specific narrative (Boris/Fiona) is suppressed in favor of generic physical reminders.';
