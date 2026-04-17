-- Migration 007: Phone verification and confirmation status
--
-- Context: yebyen/mecris#188
-- Adds a verification status to users and a table for tracking active verification codes.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT false;

COMMENT ON COLUMN users.phone_verified IS 'Indicates if the phone_number_encrypted has been verified via SMS code.';

CREATE TABLE IF NOT EXISTS phone_verifications (
    user_id VARCHAR(255) PRIMARY KEY REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE phone_verifications IS 'Temporary storage for pending SMS verification codes.';
