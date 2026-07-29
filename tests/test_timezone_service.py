"""
Tests for TimezoneService — single source of truth for US/Eastern operations.
"""
import random
import pytest
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo

from services.timezone_service import (
    EASTERN,
    today_eastern,
    day_start_eastern,
    day_end_eastern,
    daystamp,
    to_eastern,
    eastern_midnight_utc,
    is_today_eastern,
)


class TestTodayEastern:
    def test_returns_date_in_eastern(self):
        d = today_eastern()
        assert isinstance(d, date)
        # Should match system's Eastern date
        expected = datetime.now(ZoneInfo("America/New_York")).date()
        assert d == expected


class TestDayStartEastern:
    def test_defaults_to_today(self):
        dt = day_start_eastern()
        today = today_eastern()
        assert dt.date() == today
        assert dt.hour == 0 and dt.minute == 0 and dt.second == 0
        assert dt.tzinfo == EASTERN

    def test_explicit_date(self):
        d = date(2026, 7, 30)
        dt = day_start_eastern(d)
        assert dt.date() == d
        assert dt.tzinfo == EASTERN


class TestDayEndEastern:
    def test_defaults_to_today(self):
        dt = day_end_eastern()
        today = today_eastern()
        assert dt.date() == today
        assert dt.hour == 23 and dt.minute == 59 and dt.second == 59
        assert dt.tzinfo == EASTERN


class TestDaystamp:
    def test_naive_datetime_treated_as_eastern(self):
        # Naive 11pm Eastern -> daystamp should be that Eastern day
        dt = datetime(2026, 7, 30, 23, 0)
        assert daystamp(dt) == "20260730"

    def test_utc_datetime_converted_to_eastern(self):
        # 3am UTC = 11pm Eastern previous day
        dt = datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc)
        assert daystamp(dt) == "20260730"

    def test_eastern_datetime_preserved(self):
        dt = datetime(2026, 7, 30, 15, 0, tzinfo=EASTERN)
        assert daystamp(dt) == "20260730"

    def test_midnight_boundary_utc(self):
        # Midnight UTC = 8pm Eastern previous day
        dt = datetime(2026, 7, 31, 0, 0, tzinfo=timezone.utc)
        assert daystamp(dt) == "20260730"


class TestToEastern:
    def test_naive_treated_as_eastern(self):
        dt = datetime(2026, 7, 30, 15, 0)
        result = to_eastern(dt)
        assert result.tzinfo == EASTERN
        assert result.hour == 15

    def test_utc_converted(self):
        dt = datetime(2026, 7, 30, 19, 0, tzinfo=timezone.utc)
        result = to_eastern(dt)
        assert result.tzinfo == EASTERN
        assert result.hour == 15  # 3pm Eastern

    def test_eastern_unchanged(self):
        dt = datetime(2026, 7, 30, 15, 0, tzinfo=EASTERN)
        result = to_eastern(dt)
        assert result == dt


class TestEasternMidnightUtc:
    def test_converts_eastern_midnight_to_utc(self):
        d = date(2026, 7, 30)
        utc_midnight = eastern_midnight_utc(d)
        assert utc_midnight.tzinfo == timezone.utc
        # Eastern midnight = UTC 4am (EDT)
        assert utc_midnight.hour == 4
        assert utc_midnight.date() == d


class TestIsTodayEastern:
    def test_aware_eastern_today(self):
        dt = datetime.now(EASTERN)
        assert is_today_eastern(dt) is True

    def test_aware_utc_today(self):
        dt = datetime.now(timezone.utc)
        assert is_today_eastern(dt) is True

    def test_naive_treated_as_utc(self):
        # Naive treated as UTC
        dt = datetime.now(timezone.utc).replace(tzinfo=None)
        assert is_today_eastern(dt) is True

    def test_yesterday_false(self):
        yesterday = (datetime.now(EASTERN) - timedelta(days=1)).replace(hour=12, minute=0)
        assert is_today_eastern(yesterday) is False


class TestPropertyInvariants:
    """Property-based invariants that must always hold."""

    def test_daystamp_to_eastern_equiv(self):
        """daystamp(to_eastern(dt)) == daystamp(dt.astimezone(EASTERN)) for any aware dt"""
        import random
        for _ in range(100):
            # Random aware datetime in various timezones
            tz = random.choice([EASTERN, timezone.utc, ZoneInfo("Europe/London")])
            dt = datetime(
                random.randint(2020, 2030),
                random.randint(1, 12),
                random.randint(1, 28),
                random.randint(0, 23),
                random.randint(0, 59),
                tzinfo=tz,
            )
            # Both should give same Eastern daystamp
            assert daystamp(to_eastern(dt)) == daystamp(dt.astimezone(EASTERN))

    def test_daystamp_naive_consistency(self):
        """Naive datetimes always treated as Eastern"""
        for _ in range(100):
            dt = datetime(
                random.randint(2020, 2030),
                random.randint(1, 12),
                random.randint(1, 28),
                random.randint(0, 23),
                random.randint(0, 59),
            )
            # Naive should equal Eastern-aware of same wall time
            assert daystamp(dt) == daystamp(dt.replace(tzinfo=EASTERN))

    def test_day_start_eastern_aware(self):
        """day_start_eastern always returns EASTERN-aware midnight"""
        for _ in range(100):
            d = date(
                random.randint(2020, 2030),
                random.randint(1, 12),
                random.randint(1, 28),
            )
            dt = day_start_eastern(d)
            assert dt.tzinfo == EASTERN
            assert dt.hour == 0 and dt.minute == 0 and dt.second == 0