"""
Tests for ghost.archivist_logic — perform_archival_sync and archivists_round_robin.

Covers the two functions that had zero test coverage:

perform_archival_sync():
- Language sync happy path
- Language sync failure (exception caught, does not propagate)
- Physical activity: no activity today → no datapoint pushed (Reality Enforcement)
- Physical activity: activity detected → logs accordingly
- Physical activity check failure (exception caught)
- Presence upserted to ACTIVE_GHOST after sync
- Presence update failure (exception caught)
- Store unavailable → no presence update attempted

archivists_round_robin():
- Neon store unavailable → logs and returns
- get_all_users raises → logs and returns
- Users needing wakeup are synced
- Users NOT needing wakeup are skipped
- Exception for one user does not prevent others from being processed
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(last_ghost_activity=None):
    """Create a minimal mock PresenceRecord."""
    record = MagicMock()
    record.last_ghost_activity = last_ghost_activity
    record.last_human_activity = None
    return record


# ---------------------------------------------------------------------------
# perform_archival_sync
# ---------------------------------------------------------------------------

class TestPerformArchivalSync:
    """Unit tests for ghost.archivist_logic.perform_archival_sync."""

    @pytest.fixture(autouse=True)
    def _patch_store(self):
        """Default: Neon store unavailable (prevents live DB calls)."""
        with patch("ghost.archivist_logic.get_neon_store", return_value=None):
            yield

    @pytest.mark.asyncio
    async def test_language_sync_happy_path(self):
        """When language sync succeeds, info is logged and no exception raised."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(return_value={"has_activity_today": True})

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(return_value={"success": True})

        # BeeminderClient and LanguageSyncService are lazy-imported inside the function,
        # so patch at their source modules.
        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service):
            from ghost.archivist_logic import perform_archival_sync
            await perform_archival_sync("user1")

        mock_lang_service.sync_all.assert_called_once_with(user_id="user1")

    @pytest.mark.asyncio
    async def test_language_sync_failure_does_not_propagate(self):
        """Exception in language sync is caught; function continues and does not raise."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(return_value={"has_activity_today": False})

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(side_effect=RuntimeError("clozemaster down"))

        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service):
            from ghost.archivist_logic import perform_archival_sync
            # Must not raise
            await perform_archival_sync("user1")

    @pytest.mark.asyncio
    async def test_no_activity_today_does_not_push_datapoint(self):
        """Reality Enforcement: no activity → no safety datapoint is pushed."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(return_value={"has_activity_today": False})
        mock_beeminder.add_datapoint = AsyncMock()

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(return_value={"success": True})

        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service):
            from ghost.archivist_logic import perform_archival_sync
            await perform_archival_sync("user1")

        # Reality Enforcement: no 0.0 datapoint should be pushed
        mock_beeminder.add_datapoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_activity_detected_logs_without_pushing(self):
        """When activity is already detected, function logs and does not push."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(return_value={"has_activity_today": True})
        mock_beeminder.add_datapoint = AsyncMock()

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(return_value={"success": True})

        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service):
            from ghost.archivist_logic import perform_archival_sync
            await perform_archival_sync("user1")

        mock_beeminder.add_datapoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_activity_check_failure_does_not_propagate(self):
        """Exception in physical activity check is caught; function does not raise."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(side_effect=OSError("network error"))

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(return_value={"success": True})

        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service):
            from ghost.archivist_logic import perform_archival_sync
            await perform_archival_sync("user1")

    @pytest.mark.asyncio
    async def test_presence_upserted_to_active_ghost_when_store_available(self):
        """When Neon store is available, presence is updated to ACTIVE_GHOST."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(return_value={"has_activity_today": True})

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(return_value={"success": True})

        mock_store = MagicMock()

        from ghost.presence import StatusType

        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service), \
             patch("ghost.archivist_logic.get_neon_store", return_value=mock_store):
            from ghost.archivist_logic import perform_archival_sync
            await perform_archival_sync("user1")

        mock_store.upsert.assert_called_once_with("user1", StatusType.ACTIVE_GHOST, source="archivist")

    @pytest.mark.asyncio
    async def test_presence_update_failure_does_not_propagate(self):
        """Exception in presence upsert is caught; function does not raise."""
        mock_beeminder = AsyncMock()
        mock_beeminder.get_daily_activity_status = AsyncMock(return_value={"has_activity_today": True})

        mock_lang_service = AsyncMock()
        mock_lang_service.sync_all = AsyncMock(return_value={"success": True})

        mock_store = MagicMock()
        mock_store.upsert.side_effect = RuntimeError("neon write failed")

        with patch("beeminder_client.BeeminderClient", return_value=mock_beeminder), \
             patch("services.language_sync_service.LanguageSyncService", return_value=mock_lang_service), \
             patch("ghost.archivist_logic.get_neon_store", return_value=mock_store):
            from ghost.archivist_logic import perform_archival_sync
            await perform_archival_sync("user1")


# ---------------------------------------------------------------------------
# archivists_round_robin
# ---------------------------------------------------------------------------

class TestArchivistsRoundRobin:
    """Unit tests for ghost.archivist_logic.archivists_round_robin."""

    @pytest.mark.asyncio
    async def test_returns_early_when_store_unavailable(self):
        """If Neon store is None, round-robin returns without error."""
        with patch("ghost.archivist_logic.get_neon_store", return_value=None), \
             patch("ghost.archivist_logic.perform_archival_sync", new_callable=AsyncMock) as mock_sync:
            from ghost.archivist_logic import archivists_round_robin
            await archivists_round_robin()

        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_early_when_get_all_users_raises(self):
        """If get_all_users raises, round-robin catches error and returns."""
        mock_store = MagicMock()
        mock_store.get_all_users.side_effect = RuntimeError("db error")

        with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store), \
             patch("ghost.archivist_logic.perform_archival_sync", new_callable=AsyncMock) as mock_sync:
            from ghost.archivist_logic import archivists_round_robin
            await archivists_round_robin()

        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_syncs_users_that_need_wakeup(self):
        """Users whose cooldown has elapsed are synced."""
        # Record with no prior ghost activity → should wake up
        record = _make_record(last_ghost_activity=None)

        mock_store = MagicMock()
        mock_store.get_all_users.return_value = ["user-a"]
        mock_store.get.return_value = record

        with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store), \
             patch("ghost.archivist_logic.perform_archival_sync", new_callable=AsyncMock) as mock_sync:
            from ghost.archivist_logic import archivists_round_robin
            await archivists_round_robin()

        mock_sync.assert_called_once_with("user-a")

    @pytest.mark.asyncio
    async def test_skips_users_that_do_not_need_wakeup(self):
        """Users whose cooldown has NOT elapsed are skipped."""
        # Record synced 1 hour ago → cooldown (12h) not elapsed → should NOT wake up
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        record = _make_record(last_ghost_activity=one_hour_ago)

        mock_store = MagicMock()
        mock_store.get_all_users.return_value = ["user-b"]
        mock_store.get.return_value = record

        with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store), \
             patch("ghost.archivist_logic.perform_archival_sync", new_callable=AsyncMock) as mock_sync:
            from ghost.archivist_logic import archivists_round_robin
            await archivists_round_robin()

        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_for_one_user_does_not_block_others(self):
        """Per-user exceptions are caught; other users are still processed."""
        # user-a: synced 24h ago → needs wakeup
        # user-b: synced 24h ago → needs wakeup
        # user-a will raise; user-b should still be processed
        old = datetime.now(timezone.utc) - timedelta(hours=24)
        record_a = _make_record(last_ghost_activity=old)
        record_b = _make_record(last_ghost_activity=old)

        mock_store = MagicMock()
        mock_store.get_all_users.return_value = ["user-a", "user-b"]
        mock_store.get.side_effect = lambda uid: record_a if uid == "user-a" else record_b

        call_count = {"n": 0}

        async def _sync_side_effect(uid):
            call_count["n"] += 1
            if uid == "user-a":
                raise RuntimeError("user-a exploded")

        with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store), \
             patch("ghost.archivist_logic.perform_archival_sync", side_effect=_sync_side_effect):
            from ghost.archivist_logic import archivists_round_robin
            # Must not raise
            await archivists_round_robin()

        assert call_count["n"] == 2, "Both users should have been attempted"

    @pytest.mark.asyncio
    async def test_multiple_users_all_synced_when_needed(self):
        """All users needing wakeup receive exactly one sync call each."""
        old = datetime.now(timezone.utc) - timedelta(hours=24)
        records = {uid: _make_record(last_ghost_activity=old) for uid in ["u1", "u2", "u3"]}

        mock_store = MagicMock()
        mock_store.get_all_users.return_value = list(records.keys())
        mock_store.get.side_effect = lambda uid: records[uid]

        with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store), \
             patch("ghost.archivist_logic.perform_archival_sync", new_callable=AsyncMock) as mock_sync:
            from ghost.archivist_logic import archivists_round_robin
            await archivists_round_robin()

        assert mock_sync.call_count == 3
        called_users = {c.args[0] for c in mock_sync.call_args_list}
        assert called_users == {"u1", "u2", "u3"}
