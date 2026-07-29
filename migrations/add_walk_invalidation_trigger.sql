-- Migration: Add walk_inferences_change trigger for cache invalidation
-- Run: psql "$NEON_DB_URL" -f migrations/add_walk_invalidation_trigger.sql

CREATE OR REPLACE FUNCTION notify_walk_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_notify(
    'walk_inferences_change',
    json_build_object('user_id', NEW.user_id, 'op', TG_OP)::text
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS walk_inferences_change_trigger ON walk_inferences;
CREATE TRIGGER walk_inferences_change_trigger
AFTER INSERT OR UPDATE ON walk_inferences
FOR EACH ROW EXECUTE FUNCTION notify_walk_change();

-- Verify
SELECT 'walk_inferences_change trigger created' AS status;