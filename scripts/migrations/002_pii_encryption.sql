-- Migration 002: Add PII encryption columns to users and message_log tables
-- This aligns the database schema with the PII encryption task requirements.

-- 1. Update users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS beeminder_user_encrypted TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number_encrypted TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS clozemaster_email_encrypted TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS clozemaster_password_encrypted TEXT;

-- 2. Update message_log table
ALTER TABLE message_log ADD COLUMN IF NOT EXISTS status VARCHAR(50);
ALTER TABLE message_log ADD COLUMN IF NOT EXISTS error_msg TEXT;
ALTER TABLE message_log ADD COLUMN IF NOT EXISTS content TEXT;

-- 3. Data Migration (Optional - only if beeminder_user was plaintext)
-- Note: Encrypting the data requires the application's MASTER_ENCRYPTION_KEY,
-- so simple SQL cannot do it easily. Use scripts/migrate_pii_encryption.py for data migration.

COMMENT ON COLUMN users.beeminder_user_encrypted IS 'Encrypted Beeminder username.';
COMMENT ON COLUMN users.phone_number_encrypted IS 'Encrypted phone number for Twilio/WhatsApp.';
COMMENT ON COLUMN message_log.content IS 'Encrypted message content to protect PII.';
