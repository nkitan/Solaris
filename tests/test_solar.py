"""Tests for solaris.solar — known reference values, mode logic, formatting."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from solaris.solar import SolarCalculator, SolarTimes, _local_timezone_name, _now_aware


# Known reference sunrise/sunset values computed independently via astral.
# Format: (latitude, longitude, timezone, date, expected_sunrise, expected_sunset)
_REFERENCE_VALUES = [
    # Pune, Maharashtra, India — 2024-06-21 (summer solstice)
    (
        18.5, 73.8, "Asia/Kolkata",
        datetime.date(2024, 6, 21),
        datetime.datetime(2024, 6, 21, 5, 59, 35, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))),
        datetime.datetime(2024, 6, 21, 19, 13, 46, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))),
    ),
    # Pune — 2024-12-21 (winter solstice)
    (
        18.5, 73.8, "Asia/Kolkata",
        datetime.date(2024, 12, 21),
        datetime.datetime(2024, 12, 21, 7, 2, 36, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))),
        datetime.datetime(2024, 12, 21, 18, 3, 25, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))),
    ),
    # London — 2024-06-21 (BST)
    (
        51.5074, -0.1278, "Europe/London",
        datetime.date(2024, 6, 21),
        datetime.datetime(2024, 6, 21, 4, 43, 33, tzinfo=datetime.timezone(datetime.timedelta(hours=1))),
        datetime.datetime(2024, 6, 21, 21, 21, 17, tzinfo=datetime.timezone(datetime.timedelta(hours=1))),
    ),
]


# ---------------------------------------------------------------------------
# Constructor + get_times
# ---------------------------------------------------------------------------


class TestSolarCalculatorInit:
    def test_constructor_stores_location_info(self):
        calc = SolarCalculator(18.5, 73.8)
        assert calc._location.latitude == 18.5
        assert calc._location.longitude == 73.8

    def test_constructor_uses_local_timezone(self, mocker):
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )
        calc = SolarCalculator(18.5, 73.8)
        assert calc._location.timezone == "Asia/Kolkata"


class TestGetTimes:
    @pytest.mark.parametrize(
        ("lat", "lon", "tz", "date", "expected_sunrise", "expected_sunset"),
        _REFERENCE_VALUES,
    )
    def test_matches_known_reference_values(
        self,
        mocker,
        lat,
        lon,
        tz,
        date,
        expected_sunrise,
        expected_sunset,
    ):
        mocker.patch("solaris.solar._local_timezone_name", return_value=tz)

        calc = SolarCalculator(lat, lon)
        times = calc.get_times(date)

        # Allow ~5-minute tolerance since astral & manual references may differ slightly.
        sunrise_diff = abs((times.sunrise - expected_sunrise).total_seconds())
        sunset_diff = abs((times.sunset - expected_sunset).total_seconds())
        assert sunrise_diff < 300, (
            f"Sunrise off by {sunrise_diff}s — got {times.sunrise}, "
            f"expected {expected_sunrise}"
        )
        assert sunset_diff < 300, (
            f"Sunset off by {sunset_diff}s — got {times.sunset}, "
            f"expected {expected_sunset}"
        )

    def test_get_times_today_by_default(self, mocker):
        mocker.patch("solaris.solar._local_timezone_name", return_value="UTC")
        calc = SolarCalculator(0.0, 0.0)
        times = calc.get_times()
        assert times.sunrise.date() == datetime.date.today()

    def test_returns_solartimes_namedtuple(self, mocker):
        mocker.patch("solaris.solar._local_timezone_name", return_value="UTC")
        calc = SolarCalculator(0.0, 0.0)
        times = calc.get_times(datetime.date(2024, 6, 21))
        assert isinstance(times, SolarTimes)
        assert hasattr(times, "sunrise")
        assert hasattr(times, "sunset")

    def test_sunrise_before_sunset(self, mocker):
        mocker.patch("solaris.solar._local_timezone_name", return_value="UTC")
        calc = SolarCalculator(18.5, 73.8)
        times = calc.get_times(datetime.date(2024, 6, 21))
        assert times.sunrise < times.sunset

    def test_sunrise_sunset_are_timezone_aware(self, mocker):
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )
        calc = SolarCalculator(18.5, 73.8)
        times = calc.get_times(datetime.date(2024, 6, 21))
        assert times.sunrise.tzinfo is not None
        assert times.sunset.tzinfo is not None


# ---------------------------------------------------------------------------
# get_current_mode
# ---------------------------------------------------------------------------


class TestGetCurrentMode:
    def test_light_during_daytime(self, mocker):
        """Inject a fake 'now' that is between sunrise and sunset."""
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 12, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        # Force get_times to return known values for the fake-now date.
        sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 0, tzinfo=tz)
        mocker.patch.object(
            calc, "get_times", return_value=SolarTimes(sunrise, sunset)
        )

        assert calc.get_current_mode() == "light"

    def test_dark_before_sunrise(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 4, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 0, tzinfo=tz)
        mocker.patch.object(
            calc, "get_times", return_value=SolarTimes(sunrise, sunset)
        )

        assert calc.get_current_mode() == "dark"

    def test_dark_after_sunset(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 22, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 0, tzinfo=tz)
        mocker.patch.object(
            calc, "get_times", return_value=SolarTimes(sunrise, sunset)
        )

        assert calc.get_current_mode() == "dark"

    def test_fallback_to_dark_on_get_times_failure(self, mocker):
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )
        calc = SolarCalculator(18.5, 73.8)
        mocker.patch.object(
            calc, "get_times", side_effect=Exception("boom")
        )
        assert calc.get_current_mode() == "dark"


# ---------------------------------------------------------------------------
# next_transition
# ---------------------------------------------------------------------------


class TestNextTransition:
    def test_returns_sunrise_when_before_sunrise_today(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 4, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )
        # Freeze "today" too.
        with patch("solaris.solar.datetime.date") as mock_date:
            mock_date.today.return_value = datetime.date(2024, 6, 21)
            mock_date.side_effect = datetime.date  # allow other date() calls

            calc = SolarCalculator(18.5, 73.8)
            sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
            sunset = datetime.datetime(2024, 6, 21, 19, 0, tzinfo=tz)
            mocker.patch.object(
                calc, "get_times", return_value=SolarTimes(sunrise, sunset)
            )

            name, time = calc.next_transition()
            assert name == "sunrise"
            assert time == sunrise

    def test_returns_sunset_when_between_sunrise_and_sunset(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 12, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 0, tzinfo=tz)
        mocker.patch.object(
            calc, "get_times", return_value=SolarTimes(sunrise, sunset)
        )

        name, time = calc.next_transition()
        assert name == "sunset"
        assert time == sunset

    def test_falls_through_to_tomorrow_after_sunset(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 22, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        today_sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
        today_sunset = datetime.datetime(2024, 6, 21, 19, 0, tzinfo=tz)
        tomorrow_sunrise = datetime.datetime(2024, 6, 22, 5, 0, tzinfo=tz)
        tomorrow_sunset = datetime.datetime(2024, 6, 22, 19, 0, tzinfo=tz)

        def fake_get_times(date=None):
            target = date or datetime.date.today()
            if target == datetime.date(2024, 6, 21):
                return SolarTimes(today_sunrise, today_sunset)
            return SolarTimes(tomorrow_sunrise, tomorrow_sunset)

        mocker.patch.object(calc, "get_times", side_effect=fake_get_times)

        # Patch date.today() so the function picks 2024-06-21 as "today".
        with patch("solaris.solar.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2024, 6, 21)
            mock_dt.timedelta = datetime.timedelta
            mock_dt.date.side_effect = datetime.date

            name, time = calc.next_transition()
            assert name == "sunrise"
            assert time == tomorrow_sunrise


# ---------------------------------------------------------------------------
# format_countdown
# ---------------------------------------------------------------------------


class TestFormatCountdown:
    def test_hours_and_minutes(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 12, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        sunset = datetime.datetime(2024, 6, 21, 14, 30, tzinfo=tz)
        mocker.patch.object(
            calc, "next_transition", return_value=("sunset", sunset)
        )

        assert calc.format_countdown() == "Sunset in 2h 30m"

    def test_minutes_only(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 4, 15, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)
        mocker.patch.object(
            calc, "next_transition", return_value=("sunrise", sunrise)
        )

        assert calc.format_countdown() == "Sunrise in 45m"

    def test_passed_event(self, mocker):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        fake_now = datetime.datetime(2024, 6, 21, 6, 0, tzinfo=tz)
        mocker.patch("solaris.solar._now_aware", return_value=fake_now)
        mocker.patch(
            "solaris.solar._local_timezone_name", return_value="Asia/Kolkata"
        )

        calc = SolarCalculator(18.5, 73.8)
        sunrise = datetime.datetime(2024, 6, 21, 5, 0, tzinfo=tz)  # in past
        mocker.patch.object(
            calc, "next_transition", return_value=("sunrise", sunrise)
        )

        assert calc.format_countdown() == "Sunrise passed"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestNowAware:
    def test_is_timezone_aware(self):
        assert _now_aware().tzinfo is not None


class TestLocalTimezoneName:
    def test_returns_string(self):
        # Should always return _some_ valid string, even on weird systems.
        name = _local_timezone_name()
        assert isinstance(name, str)
        assert name  # non-empty

    def test_falls_back_when_localtime_and_timezone_missing(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "os.readlink", lambda p: (_ for _ in ()).throw(OSError())
        )

        # Make /etc/timezone also fail.
        from pathlib import Path as RealPath
        original_read_text = RealPath.read_text

        def fail_read_text(self, *a, **kw):
            if str(self) == "/etc/timezone":
                raise OSError("nope")
            return original_read_text(self, *a, **kw)

        monkeypatch.setattr(RealPath, "read_text", fail_read_text)

        name = _local_timezone_name()
        # Should be either a tzinfo key (e.g. "UTC", "Asia/Kolkata") or "UTC" fallback.
        assert isinstance(name, str)
