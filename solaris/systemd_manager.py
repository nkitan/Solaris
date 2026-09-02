"""Solaris systemd user unit manager.

Generates, installs, and manages two systemd user units:
  - solaris-update.service  (oneshot, applies the correct theme)
  - solaris-update.timer    (fires at today's sunrise and sunset)

After each timer fires, the service calls `solaris --auto` which applies
the theme AND rewrites the timer for the next pair of transitions —
the "self-rescheduling" pattern.  No long-running daemon is needed.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

SERVICE_NAME = "solaris-update.service"
TIMER_NAME = "solaris-update.timer"
WATCHER_SERVICE_NAME = "solaris-watcher.service"

# ---------------------------------------------------------------------------
# Unit file templates
# ---------------------------------------------------------------------------

_SERVICE_TEMPLATE = """\
[Unit]
Description=Solaris Theme Update
Documentation=https://github.com/notroot/solaris
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart={python_path} -m solaris.cli --auto
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus
"""

_TIMER_HEADER = """\
[Unit]
Description=Solaris Theme Transition Timer
Documentation=https://github.com/notroot/solaris

[Timer]
"""

_TIMER_FOOTER = """\
Persistent=true

[Install]
WantedBy=timers.target
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_systemctl(*args: str) -> bool:
    """Run `systemctl --user <args>` and return True on success.

    Args:
        *args: Arguments to pass to systemctl after `--user`.

    Returns:
        True if the command exited with code 0, False otherwise.
    """
    command = ["systemctl", "--user", *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.warning(
            "systemctl --user %s failed (rc=%d): %s",
            " ".join(args), result.returncode, result.stderr.strip(),
        )
        return False
    return True


def _format_on_calendar(dt_aware) -> str:
    """Format a timezone-aware datetime as a systemd OnCalendar value.

    Uses local time (the timer runs on the local machine) in the format:
      *-*-* HH:MM:00

    Args:
        dt_aware: A timezone-aware datetime object.

    Returns:
        A systemd OnCalendar string in local time.
    """
    import datetime  # local import to keep module-level imports minimal
    local_dt = dt_aware.astimezone(tz=None)  # convert to local timezone
    return local_dt.strftime("*-*-* %H:%M:00")


def _build_timer_content(sunrise_cal: str, sunset_cal: str) -> str:
    """Assemble the full .timer unit file content.

    Two OnCalendar lines are used — one for sunrise, one for sunset —
    so a single timer handles both transitions each day.

    Args:
        sunrise_cal: Formatted OnCalendar string for sunrise.
        sunset_cal:  Formatted OnCalendar string for sunset.

    Returns:
        Complete .timer unit file as a string.
    """
    return (
        _TIMER_HEADER
        + f"OnCalendar={sunrise_cal}\n"
        + f"OnCalendar={sunset_cal}\n"
        + _TIMER_FOOTER
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_units(sunrise, sunset) -> None:
    """Write both unit files to disk and reload the systemd daemon.

    Creates ~/.config/systemd/user/ if it doesn't exist.

    Args:
        sunrise: A timezone-aware datetime for today's sunrise.
        sunset:  A timezone-aware datetime for today's sunset.
    """
    UNIT_DIR.mkdir(parents=True, exist_ok=True)

    service_content = _SERVICE_TEMPLATE.format(python_path=sys.executable)
    service_path = UNIT_DIR / SERVICE_NAME
    service_path.write_text(service_content, encoding="utf-8")
    logger.info("Wrote %s", service_path)

    update_timer(sunrise, sunset)


def update_timer(sunrise, sunset) -> None:
    """Rewrite the timer unit with new OnCalendar values and reload the daemon.

    Safe to call even if the timer is already running — systemd will pick up
    the new file content after daemon-reload and timer restart.

    Args:
        sunrise: A timezone-aware datetime for the target sunrise.
        sunset:  A timezone-aware datetime for the target sunset.
    """
    sunrise_cal = _format_on_calendar(sunrise)
    sunset_cal = _format_on_calendar(sunset)

    timer_content = _build_timer_content(sunrise_cal, sunset_cal)

    timer_path = UNIT_DIR / TIMER_NAME
    timer_path.write_text(timer_content, encoding="utf-8")
    logger.info(
        "Wrote timer: sunrise=%s sunset=%s → %s", sunrise_cal, sunset_cal, timer_path
    )

    _run_systemctl("daemon-reload")


def enable() -> None:
    """Enable and start the Solaris timer.

    Equivalent to: systemctl --user enable --now solaris-update.timer
    """
    success = _run_systemctl("enable", "--now", TIMER_NAME)
    if success:
        logger.info("Solaris timer enabled and started.")
    else:
        logger.error("Failed to enable Solaris timer.")


def disable() -> None:
    """Stop and disable the Solaris timer.

    Equivalent to: systemctl --user disable --now solaris-update.timer
    """
    success = _run_systemctl("disable", "--now", TIMER_NAME)
    if success:
        logger.info("Solaris timer disabled.")
    else:
        logger.error("Failed to disable Solaris timer.")


def is_enabled() -> bool:
    """Return True if the Solaris timer unit is currently enabled.

    Returns:
        True if `systemctl --user is-enabled solaris-update.timer` exits 0.
    """
    result = subprocess.run(
        ["systemctl", "--user", "is-enabled", TIMER_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def is_active() -> bool:
    """Return True if the Solaris timer unit is currently active (running).

    Returns:
        True if `systemctl --user is-active solaris-update.timer` exits 0.
    """
    result = subprocess.run(
        ["systemctl", "--user", "is-active", TIMER_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def trigger_now() -> None:
    """Manually trigger a one-shot execution of the Solaris service.

    Equivalent to: systemctl --user start solaris-update.service
    """
    success = _run_systemctl("start", SERVICE_NAME)
    if success:
        logger.info("Solaris service triggered manually.")
    else:
        logger.error("Failed to trigger Solaris service.")


def update_timer_time_based(light_start: str, dark_start: str) -> None:
    """Rewrite the timer unit with two fixed daily OnCalendar entries.

    Use this when schedule_mode is "time".  The timer fires at the same
    clock times every day regardless of sunrise/sunset.

    Args:
        light_start: 24-hour HH:MM string for when to switch TO light mode.
        dark_start:  24-hour HH:MM string for when to switch TO dark mode.
    """
    light_cal = f"*-*-* {light_start}:00"
    dark_cal = f"*-*-* {dark_start}:00"

    timer_content = _build_timer_content(light_cal, dark_cal)

    timer_path = UNIT_DIR / TIMER_NAME
    timer_path.write_text(timer_content, encoding="utf-8")
    logger.info(
        "Wrote time-based timer: light=%s dark=%s → %s",
        light_cal, dark_cal, timer_path,
    )

    _run_systemctl("daemon-reload")


# ---------------------------------------------------------------------------
# Dark Style Watcher service
# ---------------------------------------------------------------------------

_WATCHER_SERVICE_TEMPLATE = """\
[Unit]
Description=Solaris Dark Style Watcher
Documentation=https://github.com/notroot/solaris
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={python_path} -m solaris.cli --watch
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus

[Install]
WantedBy=graphical-session.target
"""


def install_watcher_service() -> None:
    """Write the solaris-watcher.service unit file and reload the daemon.

    This is a long-running (Type=simple) service that listens to the
    GNOME color-scheme GSettings key and syncs themes in real time.
    """
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    service_content = _WATCHER_SERVICE_TEMPLATE.format(python_path=sys.executable)
    service_path = UNIT_DIR / WATCHER_SERVICE_NAME
    service_path.write_text(service_content, encoding="utf-8")
    logger.info("Wrote %s", service_path)
    _run_systemctl("daemon-reload")


def enable_watcher() -> None:
    """Enable and immediately start the Dark Style watcher service.

    Equivalent to: systemctl --user enable --now solaris-watcher.service
    """
    install_watcher_service()
    success = _run_systemctl("enable", "--now", WATCHER_SERVICE_NAME)
    if success:
        logger.info("Dark Style watcher enabled and started.")
    else:
        logger.error("Failed to enable Dark Style watcher.")


def disable_watcher() -> None:
    """Stop and disable the Dark Style watcher service.

    Equivalent to: systemctl --user disable --now solaris-watcher.service
    """
    success = _run_systemctl("disable", "--now", WATCHER_SERVICE_NAME)
    if success:
        logger.info("Dark Style watcher disabled.")
    else:
        logger.error("Failed to disable Dark Style watcher.")


def is_watcher_active() -> bool:
    """Return True if the Dark Style watcher service is currently running.

    Returns:
        True if `systemctl --user is-active solaris-watcher.service` exits 0.
    """
    result = subprocess.run(
        ["systemctl", "--user", "is-active", WATCHER_SERVICE_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def is_watcher_enabled() -> bool:
    """Return True if the Dark Style watcher service is enabled at login.

    Returns:
        True if `systemctl --user is-enabled solaris-watcher.service` exits 0.
    """
    result = subprocess.run(
        ["systemctl", "--user", "is-enabled", WATCHER_SERVICE_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0
