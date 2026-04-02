"""
Tests for ghost.presence — cooperative presence lock for ghost sessions.

Covers:
- acquire_lock / release_lock round-trip
- check_presence with no lock (no human present)
- check_presence with a fresh lock (human present)
- check_presence with a stale lock (TTL expired → human gone)
- presence_lock context manager (auto-release on exit)
- presence_lock context manager releases lock even on exception
"""

import os
import time
import pytest

from ghost.presence import (
    acquire_lock,
    release_lock,
    check_presence,
    presence_lock,
    PRESENCE_TTL_SECONDS,
)


@pytest.fixture
def lock_file(tmp_path):
    """Return a deterministic lock path inside a temp dir (auto-cleaned)."""
    return str(tmp_path / "presence.lock")


class TestAcquireRelease:
    def test_acquire_creates_file(self, lock_file):
        acquire_lock(lock_file)
        assert os.path.exists(lock_file)

    def test_acquire_returns_lock_path(self, lock_file):
        result = acquire_lock(lock_file)
        assert result == lock_file

    def test_acquire_writes_timestamp(self, lock_file):
        before = int(time.time())
        acquire_lock(lock_file)
        after = int(time.time())
        content = int(open(lock_file).read().strip())
        assert before <= content <= after

    def test_release_removes_file(self, lock_file):
        acquire_lock(lock_file)
        release_lock(lock_file)
        assert not os.path.exists(lock_file)

    def test_release_returns_true_when_lock_existed(self, lock_file):
        acquire_lock(lock_file)
        assert release_lock(lock_file) is True

    def test_release_returns_false_when_no_lock(self, lock_file):
        assert release_lock(lock_file) is False

    def test_acquire_release_roundtrip(self, lock_file):
        acquire_lock(lock_file)
        assert os.path.exists(lock_file)
        release_lock(lock_file)
        assert not os.path.exists(lock_file)


class TestCheckPresence:
    def test_no_lock_means_no_human(self, lock_file):
        status = check_presence(lock_file)
        assert not status.lock_exists
        assert not status.human_present
        assert status.age_seconds is None

    def test_fresh_lock_means_human_present(self, lock_file):
        acquire_lock(lock_file)
        status = check_presence(lock_file)
        assert status.lock_exists
        assert status.human_present
        assert status.age_seconds is not None
        assert status.age_seconds < PRESENCE_TTL_SECONDS

    def test_stale_lock_means_human_gone(self, lock_file):
        acquire_lock(lock_file)
        # Backdate the file modification time to simulate an old lock
        old_time = time.time() - PRESENCE_TTL_SECONDS - 60
        os.utime(lock_file, (old_time, old_time))
        status = check_presence(lock_file)
        assert status.lock_exists
        assert not status.human_present
        assert status.age_seconds > PRESENCE_TTL_SECONDS

    def test_custom_ttl_respected(self, lock_file):
        acquire_lock(lock_file)
        # With a 0-second TTL even a brand-new lock is "stale"
        status = check_presence(lock_file, ttl=0)
        assert not status.human_present

    def test_status_includes_lock_path(self, lock_file):
        status = check_presence(lock_file)
        assert status.lock_path == lock_file


class TestPresenceLockContextManager:
    def test_creates_and_removes_lock(self, lock_file):
        with presence_lock(lock_file):
            assert os.path.exists(lock_file)
        assert not os.path.exists(lock_file)

    def test_yields_lock_path(self, lock_file):
        with presence_lock(lock_file) as path:
            assert path == lock_file

    def test_releases_on_exception(self, lock_file):
        try:
            with presence_lock(lock_file):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert not os.path.exists(lock_file)

    def test_second_session_detects_lock(self, lock_file):
        """Simulates two concurrent ghost sessions: the first holds the lock,
        the second should see human_present=True and defer."""
        with presence_lock(lock_file):
            status = check_presence(lock_file)
            assert status.lock_exists
            # The lock is fresh — a second session would yield here
            assert status.human_present
