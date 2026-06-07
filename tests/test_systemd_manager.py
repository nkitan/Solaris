"""Tests for solaris.systemd_manager — generated unit file content and systemctl wrappers."""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from solaris import systemd_manager


@pytest.fixture
def fake_unit_dir(tmp_path, monkeypatch):
    """Redirect UNIT_DIR to a temp path so file writes don't touch real systemd."""
    unit_dir = tmp_path / "systemd-user"
    monkeypatch.setattr(systemd_manager, "UNIT_DIR", unit_dir)
    return unit_dir


def _make_completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# _format_on_calendar
# ---------------------------------------------------------------------------


class TestFormatOnCalendar:
    def test_formats_to_systemd_oncalendar_string(self):
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        dt = datetime.datetime(2024, 6, 21, 5, 59, 35, tzinfo=tz)
        result = systemd_manager._format_on_calendar(dt)
        # Format: *-*-* HH:MM:00 (in local time)
        assert result.startswith("*-*-* ")
        assert result.endswith(":00")
        assert ":" in result.split(" ")[1]


# ---------------------------------------------------------------------------
# _build_timer_content
# ---------------------------------------------------------------------------


class TestBuildTimerContent:
    def test_contains_both_oncalendar_lines(self):
        content = systemd_manager._build_timer_content(
            "*-*-* 06:00:00", "*-*-* 18:00:00"
        )
        assert "OnCalendar=*-*-* 06:00:00" in content
        assert "OnCalendar=*-*-* 18:00:00" in content

    def test_contains_required_sections(self):
        content = systemd_manager._build_timer_content("*-*-* 06:00:00", "*-*-* 18:00:00")
        assert "[Unit]" in content
        assert "[Timer]" in content
        assert "[Install]" in content

    def test_persistent_is_true(self):
        content = systemd_manager._build_timer_content("*-*-* 06:00:00", "*-*-* 18:00:00")
        assert "Persistent=true" in content

    def test_wantedby_timers_target(self):
        content = systemd_manager._build_timer_content("*-*-* 06:00:00", "*-*-* 18:00:00")
        assert "WantedBy=timers.target" in content


# ---------------------------------------------------------------------------
# install_units / update_timer
# ---------------------------------------------------------------------------


class TestInstallUnits:
    def test_writes_both_service_and_timer(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        systemd_manager.install_units(sunrise, sunset)

        service_file = fake_unit_dir / systemd_manager.SERVICE_NAME
        timer_file = fake_unit_dir / systemd_manager.TIMER_NAME

        assert service_file.exists()
        assert timer_file.exists()

    def test_service_unit_content(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        systemd_manager.install_units(sunrise, sunset)

        service = (fake_unit_dir / systemd_manager.SERVICE_NAME).read_text()
        assert "[Unit]" in service
        assert "[Service]" in service
        assert "Type=oneshot" in service
        assert "ExecStart=" in service
        assert "--auto" in service
        assert sys.executable in service

    def test_timer_unit_content(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        systemd_manager.install_units(sunrise, sunset)

        timer = (fake_unit_dir / systemd_manager.TIMER_NAME).read_text()
        assert timer.count("OnCalendar=") == 2
        assert "Persistent=true" in timer

    def test_calls_daemon_reload(self, fake_unit_dir, mocker):
        run = mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        systemd_manager.install_units(sunrise, sunset)

        call_args = [c.args[0] for c in run.call_args_list]
        assert any("daemon-reload" in a for a in call_args)

    def test_creates_unit_dir_if_missing(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        # fake_unit_dir does NOT exist yet
        assert not fake_unit_dir.exists()

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        systemd_manager.install_units(sunrise, sunset)
        assert fake_unit_dir.is_dir()


class TestUpdateTimer:
    def test_rewrites_timer_only(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        fake_unit_dir.mkdir(parents=True, exist_ok=True)
        systemd_manager.update_timer(sunrise, sunset)

        assert (fake_unit_dir / systemd_manager.TIMER_NAME).exists()
        # Service should NOT have been written by update_timer alone.
        assert not (fake_unit_dir / systemd_manager.SERVICE_NAME).exists()

    def test_overwrites_existing_timer(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        fake_unit_dir.mkdir(parents=True, exist_ok=True)
        (fake_unit_dir / systemd_manager.TIMER_NAME).write_text("old content")

        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        sunrise = datetime.datetime(2024, 6, 21, 5, 59, tzinfo=tz)
        sunset = datetime.datetime(2024, 6, 21, 19, 13, tzinfo=tz)

        systemd_manager.update_timer(sunrise, sunset)

        new_content = (fake_unit_dir / systemd_manager.TIMER_NAME).read_text()
        assert "old content" not in new_content
        assert "OnCalendar=" in new_content


class TestUpdateTimerTimeBased:
    def test_writes_fixed_oncalendar_entries(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )
        fake_unit_dir.mkdir(parents=True, exist_ok=True)

        systemd_manager.update_timer_time_based("07:00", "20:00")

        content = (fake_unit_dir / systemd_manager.TIMER_NAME).read_text()
        assert "OnCalendar=*-*-* 07:00:00" in content
        assert "OnCalendar=*-*-* 20:00:00" in content


# ---------------------------------------------------------------------------
# enable / disable / is_enabled / is_active / trigger_now
# ---------------------------------------------------------------------------


class TestSystemctlWrappers:
    def test_enable_calls_systemctl(self, mocker):
        run = mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )
        systemd_manager.enable()
        args = run.call_args.args[0]
        assert args[:2] == ["systemctl", "--user"]
        assert "enable" in args
        assert "--now" in args
        assert systemd_manager.TIMER_NAME in args

    def test_disable_calls_systemctl(self, mocker):
        run = mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )
        systemd_manager.disable()
        args = run.call_args.args[0]
        assert "disable" in args
        assert "--now" in args

    def test_is_enabled_true(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=0),
        )
        assert systemd_manager.is_enabled() is True

    def test_is_enabled_false(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        assert systemd_manager.is_enabled() is False

    def test_is_active_true(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=0),
        )
        assert systemd_manager.is_active() is True

    def test_is_active_false(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=3),
        )
        assert systemd_manager.is_active() is False

    def test_trigger_now(self, mocker):
        run = mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )
        systemd_manager.trigger_now()
        args = run.call_args.args[0]
        assert "start" in args
        assert systemd_manager.SERVICE_NAME in args

    def test_enable_logs_error_on_failure(self, mocker, caplog):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=1, stderr="nope"),
        )
        with caplog.at_level("ERROR"):
            systemd_manager.enable()
        assert any("Failed to enable" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Watcher service helpers
# ---------------------------------------------------------------------------


class TestWatcherService:
    def test_install_watcher_writes_service_file(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        systemd_manager.install_watcher_service()

        service_path = fake_unit_dir / systemd_manager.WATCHER_SERVICE_NAME
        assert service_path.exists()
        content = service_path.read_text()
        assert "Type=simple" in content
        assert "Restart=on-failure" in content
        assert "--watch" in content
        assert sys.executable in content

    def test_enable_watcher_installs_and_enables(self, fake_unit_dir, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )

        systemd_manager.enable_watcher()
        path = fake_unit_dir / systemd_manager.WATCHER_SERVICE_NAME
        assert path.exists()

    def test_disable_watcher_calls_systemctl(self, mocker):
        run = mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(),
        )
        systemd_manager.disable_watcher()
        args = run.call_args.args[0]
        assert "disable" in args
        assert systemd_manager.WATCHER_SERVICE_NAME in args

    def test_is_watcher_active_true(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=0),
        )
        assert systemd_manager.is_watcher_active() is True

    def test_is_watcher_active_false(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=3),
        )
        assert systemd_manager.is_watcher_active() is False

    def test_is_watcher_enabled_true(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=0),
        )
        assert systemd_manager.is_watcher_enabled() is True

    def test_is_watcher_enabled_false(self, mocker):
        mocker.patch(
            "solaris.systemd_manager.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        assert systemd_manager.is_watcher_enabled() is False
