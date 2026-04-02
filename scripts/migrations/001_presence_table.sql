-- Migration 001: Create presence table for Neon-backed ghost coordination
-- Replaces file-based presence.lock with a globally-visible presence record.
--
-- Status types:
--   pulse           — background system heartbeat (bot is alive)
--   active_human    — a human is actively using the CLI or workspace
--   needs_attention — bot requesting human review/decision
--   pound_sand      — human denying bot attention (back off)
--   shits_on_fire_yo (SOFY) — bot emergency override, overrides pound_sand
--
-- Run once against your Neon database:
--   psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'presence_status_type') THEN
        CREATE TYPE presence_status_type AS ENUM (
            'pulse',
            'active_human',
            'needs_attention',
            'pound_sand',
            'shits_on_fire_yo'
        );
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS presence (
    user_id     TEXT                  PRIMARY KEY,
    last_active TIMESTAMPTZ           NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    source      TEXT                  NOT NULL DEFAULT 'cli',
    status_type presence_status_type  NOT NULL DEFAULT 'pulse'
);

COMMENT ON TABLE presence IS
    'Single-row-per-user cooperative presence state for Mecris ghost sessions.';
COMMENT ON COLUMN presence.user_id IS
    'Pocket ID sub (same as users.pocket_id_sub).';
COMMENT ON COLUMN presence.last_active IS
    'UTC timestamp of last status upsert.';
COMMENT ON COLUMN presence.source IS
    'Origin of the last status update: cli, web, android, or bot.';
COMMENT ON COLUMN presence.status_type IS
    'Current presence/attention state. See type definition above.';
