"""Solaris solar calculation module.

Thin, testable wrapper around the `astral` library.
All I/O is limited to reading the system clock; no disk or network access.
"""

from __future__ import annotations

import datetime
import logging
from typing import NamedTuple

from astral import LocationInfo
from astral.sun import sun

logger = logging.getLogger(__name__)


class SolarTimes(NamedTuple):
    """Sunrise and sunset times for a single day, in local time."""

    sunrise: datetime.datetime
    sunset: datetime.datetime


class SolarCalculator:
    """Calculates sunrise, sunset, and current light/dark mode for a location.

    Args:
        latitude:  Geographic latitude in decimal degrees (-90 to 90).
        longitude: Geographic longitude in decimal degrees (-180 to 180).
    """

    def __init__(self, latitude: float, longitude: float) -> None:
        self._location = LocationInfo(
            name="Solaris Location",
            region="",
            timezone=_local_timezone_name(),
            latitude=latitude,
            longitude=longitude,
        )
        logger.debug(
            "SolarCalculator initialised for (%.4f, %.4f) tz=%s",
            latitude, longitude, self._location.timezone,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_times(self, date: datetime.date | None = None) -> SolarTimes:
        """Return sunrise and sunset times for a given date.

        Args:
            date: The date to calculate for. Defaults to today (local time).

        Returns:
            A SolarTimes namedtuple with timezone-aware datetimes.
        """
        target_date = date or datetime.date.today()

        try:
            solar_data = sun(self._location.observer, date=target_date, tzinfo=self._location.timezone)
        except Exception as exc:
            logger.error("Failed to calculate solar times for %s: %s", target_date, exc)
            raise

        return SolarTimes(
            sunrise=solar_data["sunrise"],
            sunset=solar_data["sunset"],
        )

    def get_current_mode(self) -> str:
        """Determine whether it is currently day (light) or night (dark).

        Returns:
            "light" if the current time is between sunrise and sunset,
            "dark"  otherwise.
        """
        now = _now_aware()
        try:
            times = self.get_times()
        except Exception:
            logger.warning("Solar calculation failed — defaulting to 'dark'.")
            return "dark"

        if times.sunrise <= now <= times.sunset:
            return "light"
        return "dark"

    def next_transition(self) -> tuple[str, datetime.datetime]:
        """Return the name and datetime of the next sunrise/sunset transition.

        Looks ahead up to two days to find the next event.

        Returns:
            A tuple of (event_name, datetime) where event_name is
            "sunrise" or "sunset".

        Raises:
            RuntimeError: If solar times cannot be calculated for any candidate date.
        """
        now = _now_aware()
        last_exc: Exception | None = None

        # Check today's remaining transitions, then tomorrow's.
        for day_offset in range(2):
            candidate_date = datetime.date.today() + datetime.timedelta(days=day_offset)
            try:
                times = self.get_times(candidate_date)
            except Exception as exc:
                last_exc = exc
                continue

            if now < times.sunrise:
                return ("sunrise", times.sunrise)
            if now < times.sunset:
                return ("sunset", times.sunset)

        # Extreme fallback: attempt tomorrow's sunrise explicitly.
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        try:
            times = self.get_times(tomorrow)
            return ("sunrise", times.sunrise)
        except Exception as exc:
            raise RuntimeError(
                f"Cannot calculate next solar transition: {exc}"
            ) from (last_exc or exc)

    def format_countdown(self) -> str:
        """Format the time remaining until the next transition as a human string.

        Returns:
            A string like "Sunset in 2h 34m" or "Sunrise in 45m".
        """
        event_name, event_time = self.next_transition()
        now = _now_aware()
        remaining = event_time - now

        total_seconds = int(remaining.total_seconds())
        if total_seconds < 0:
            return f"{event_name.capitalize()} passed"

        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60

        if hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"

        return f"{event_name.capitalize()} in {time_str}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _local_timezone_name() -> str:
    """Return the IANA timezone name for the local system.

    Resolution order:
    1. /etc/localtime symlink target (most reliable on Arch Linux)
    2. /etc/timezone file content
    3. zoneinfo.ZoneInfo key from the current local tzinfo object
    4. UTC as a safe fallback
    """
    import os
    import zoneinfo

    # 1. Read /etc/localtime symlink (Arch Linux standard)
    localtime_path = "/etc/localtime"
    try:
        link_target = os.readlink(localtime_path)
        # Typical: /usr/share/zoneinfo/Asia/Kolkata
        marker = "/zoneinfo/"
        idx = link_target.find(marker)
        if idx != -1:
            return link_target[idx + len(marker):]
    except (OSError, ValueError):
        pass

    # 2. /etc/timezone plain-text file
    try:
        return Path("/etc/timezone").read_text(encoding="utf-8").strip()
    except OSError:
        pass

    # 3. zoneinfo key on the tzinfo object
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    tz_key = getattr(local_tz, "key", None)
    if tz_key:
        return tz_key

    # 4. Safe fallback
    logger.warning("Could not determine IANA timezone — defaulting to UTC.")
    return "UTC"


def _now_aware() -> datetime.datetime:
    """Return the current local time as a timezone-aware datetime."""
    return datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
