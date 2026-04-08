-- Migration 003: Add user_id scoping to language_stats and budget_tracking
-- Implements multi-tenancy foundation from kingdonb/mecris#120.
--
-- This migration is idempotent: all statements use IF NOT EXISTS / IF EXISTS
-- guards so it can be re-run safely against an already-migrated schema.
--
-- Run once against your Neon database:
--   psql $NEON_DB_URL -f scripts/migrations/003_multi_tenancy.sql

-- 1. Add user_id column to language_stats (if absent)
ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE;

-- 2. Backfill user_id for any legacy rows that predate multi-tenancy
UPDATE language_stats
SET user_id = (SELECT pocket_id_sub FROM users LIMIT 1)
WHERE user_id IS NULL;

-- 3. Migrate language_stats primary key from (language_name) to (user_id, language_name)
--    Guard: only drop the old single-column PK if the new composite one does not yet exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'language_stats_pkey'
          AND contype = 'p'
          AND (
            SELECT COUNT(*) FROM pg_attribute a
            JOIN pg_index i ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indexrelid
            WHERE c.relname = 'language_stats_pkey' AND a.attname = 'user_id'
          ) > 0
    ) THEN
        -- Old single-column primary key exists — replace it
        ALTER TABLE language_stats DROP CONSTRAINT IF EXISTS language_stats_pkey;
        ALTER TABLE language_stats ADD PRIMARY KEY (user_id, language_name);
    END IF;
END$$;

-- 4. Add user_id column to budget_tracking (if absent)
ALTER TABLE budget_tracking ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE;

-- 5. Backfill budget_tracking rows
UPDATE budget_tracking
SET user_id = (SELECT pocket_id_sub FROM users LIMIT 1)
WHERE user_id IS NULL;

-- Comments
COMMENT ON COLUMN language_stats.user_id IS
    'Owner of this language stat row (Pocket ID sub). Part of composite primary key.';
COMMENT ON COLUMN budget_tracking.user_id IS
    'Owner of this budget record (Pocket ID sub). Scopes all budget queries.';
