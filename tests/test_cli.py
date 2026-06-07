"""Tests for solaris.cli — argument parsing and handler dispatch."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from solaris import cli
from solaris.config import (
    SCHEDULE_MODE_MANUAL,
    SCHEDULE_MODE_SOLAR,
    SCHEDULE_MODE_TIME,
    SolarisConfig,
)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_apply_light_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--apply-light"])
        assert args.apply_light is True

    def test_apply_dark_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--apply-dark"])
        assert args.apply_dark is True

    def test_auto_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--auto"])
        assert args.auto is True

    def test_status_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--status"])
        assert args.status is True

    def test_install_timer_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--install-timer"])
        assert args.install_timer is True

    def test_update_timer_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--update-timer"])
        assert args.update_timer is True

    def test_watch_flag_parses(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--watch"])
        assert args.watch is True

    def test_verbose_flag(self):
        parser = cli._build_parser()
        args = parser.parse_args(["--status", "-v"])
        assert args.verbose is True

    def test_mutual_exclusion_enforced(self):
        parser = cli._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--apply-light", "--apply-dark"])

    def test_at_least_one_required(self):
        parser = cli._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


# ---------------------------------------------------------------------------
# Handler dispatch via main()
# ---------------------------------------------------------------------------


class TestMainDispatch:
    def test_main_apply_light_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--apply-light"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_apply_light")

        cli.main()
        handler.assert_called_once()

    def test_main_apply_dark_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--apply-dark"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_apply_dark")

        cli.main()
        handler.assert_called_once()

    def test_main_status_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--status"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_status")

        cli.main()
        handler.assert_called_once()

    def test_main_auto_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--auto"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_auto")

        cli.main()
        handler.assert_called_once()

    def test_main_install_timer_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--install-timer"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_install_timer")

        cli.main()
        handler.assert_called_once()

    def test_main_update_timer_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--update-timer"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_update_timer")

        cli.main()
        handler.assert_called_once()

    def test_main_watch_calls_handler(self, mocker):
        mocker.patch("sys.argv", ["solaris", "--watch"])
        mocker.patch("solaris.cli.config_module.load", return_value=SolarisConfig())
        handler = mocker.patch("solaris.cli._handle_watch")

        cli.main()
        handler.assert_called_once()


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------


class TestHandleApplyLight:
    def test_calls_theme_engine_apply_light(self, mocker, capsys):
        mock = mocker.patch("solaris.cli.theme_engine.apply_light")
        mocker.patch("solaris.cli.firefox.apply_theme")
        mocker.patch("solaris.cli.ghostty.apply_theme")

        cli._handle_apply_light(SolarisConfig())
        mock.assert_called_once()
        out = capsys.readouterr().out
        assert "Light" in out

    def test_skips_firefox_when_disabled(self, mocker):
        mocker.patch("solaris.cli.theme_engine.apply_light")
        ff = mocker.patch("solaris.cli.firefox.apply_theme")
        gh = mocker.patch("solaris.cli.ghostty.apply_theme")

        cfg = SolarisConfig(firefox_integration=False, ghostty_integration=False)
        cli._handle_apply_light(cfg)
        ff.assert_not_called()
        gh.assert_not_called()


class TestHandleApplyDark:
    def test_calls_theme_engine_apply_dark(self, mocker, capsys):
        mock = mocker.patch("solaris.cli.theme_engine.apply_dark")
        mocker.patch("solaris.cli.firefox.apply_theme")
        mocker.patch("solaris.cli.ghostty.apply_theme")

        cli._handle_apply_dark(SolarisConfig())
        mock.assert_called_once()
        out = capsys.readouterr().out
        assert "Dark" in out


class TestDetermineTimeMode:
    def _freeze_datetime(self, mocker, fake_now: datetime.datetime):
        """Patch the `datetime` module *as referenced by cli._determine_time_mode*.

        Because _determine_time_mode does `import datetime` at call time, the
        real `datetime` module is imported each call — we patch the actual
        `datetime.datetime` class so `.now()` returns our fake.
        """
        real_dt_cls = datetime.datetime

        class FakeDateTime(real_dt_cls):
            @classmethod
            def now(cls, tz=None):
                if tz is not None:
                    return fake_now.replace(tzinfo=tz)
                return fake_now

        mocker.patch("datetime.datetime", FakeDateTime)

    def test_light_during_normal_window(self, mocker):
        self._freeze_datetime(mocker, datetime.datetime(2024, 6, 21, 12, 0))
        cfg = SolarisConfig(
            schedule_mode=SCHEDULE_MODE_TIME,
            time_light_start="07:00",
            time_dark_start="20:00",
        )
        assert cli._determine_time_mode(cfg) == "light"

    def test_dark_at_night_normal_window(self, mocker):
        self._freeze_datetime(mocker, datetime.datetime(2024, 6, 21, 23, 0))
        cfg = SolarisConfig(
            schedule_mode=SCHEDULE_MODE_TIME,
            time_light_start="07:00",
            time_dark_start="20:00",
        )
        assert cli._determine_time_mode(cfg) == "dark"

    def test_dark_before_light_start(self, mocker):
        self._freeze_datetime(mocker, datetime.datetime(2024, 6, 21, 5, 0))
        cfg = SolarisConfig(
            schedule_mode=SCHEDULE_MODE_TIME,
            time_light_start="07:00",
            time_dark_start="20:00",
        )
        assert cli._determine_time_mode(cfg) == "dark"

    def test_inverted_window_dark_at_midnight(self, mocker):
        # light_start=20:00, dark_start=07:00 — inverted: dark spans 07:00-20:00
        self._freeze_datetime(mocker, datetime.datetime(2024, 6, 21, 12, 0))
        cfg = SolarisConfig(
            schedule_mode=SCHEDULE_MODE_TIME,
            time_light_start="20:00",
            time_dark_start="07:00",
        )
        assert cli._determine_time_mode(cfg) == "dark"


class TestHandleAuto:
    def test_manual_mode_applies_configured_mode(self, mocker):
        mocker.patch("solaris.cli.theme_engine.apply_dark")
        mocker.patch("solaris.cli.firefox.apply_theme")
        mocker.patch("solaris.cli.ghostty.apply_theme")
        apply_dark_handler = mocker.patch("solaris.cli._handle_apply_dark")

        cfg = SolarisConfig(
            schedule_mode=SCHEDULE_MODE_MANUAL,
            manual_mode="dark",
        )
        cli._handle_auto(cfg)
        apply_dark_handler.assert_called_once_with(cfg)

    def test_solar_mode_uses_calculator(self, mocker):
        mock_calc = MagicMock()
        mock_calc.get_current_mode.return_value = "light"
        mock_calc.get_times.return_value = MagicMock(
            sunrise=datetime.datetime.now(datetime.timezone.utc),
            sunset=datetime.datetime.now(datetime.timezone.utc),
        )
        mocker.patch(
            "solaris.cli.SolarCalculator", return_value=mock_calc
        )
        mocker.patch("solaris.cli.systemd_manager.update_timer")
        apply_light_handler = mocker.patch("solaris.cli._handle_apply_light")

        cfg = SolarisConfig(schedule_mode=SCHEDULE_MODE_SOLAR)
        cli._handle_auto(cfg)

        apply_light_handler.assert_called_once()
        mock_calc.get_current_mode.assert_called_once()


class TestHandleStatus:
    def test_prints_version_and_mode(self, mocker, capsys):
        mocker.patch(
            "solaris.cli.theme_engine.get_current_mode", return_value="light"
        )
        mocker.patch("solaris.cli.systemd_manager.is_active", return_value=False)
        mocker.patch("solaris.cli.systemd_manager.is_enabled", return_value=False)
        mocker.patch(
            "solaris.cli.systemd_manager.is_watcher_active", return_value=False
        )
        mocker.patch(
            "solaris.cli.systemd_manager.is_watcher_enabled", return_value=False
        )

        mock_calc = MagicMock()
        mock_calc.format_countdown.return_value = "Sunset in 2h 30m"
        mocker.patch("solaris.cli.SolarCalculator", return_value=mock_calc)

        cli._handle_status(SolarisConfig())
        out = capsys.readouterr().out
        assert "Solaris" in out
        assert "light" in out
        assert "Sunset in 2h 30m" in out


class TestHandleInstallTimer:
    def test_solar_mode_installs_units(self, mocker, capsys):
        mock_calc = MagicMock()
        sunrise = datetime.datetime(
            2024, 6, 21, 5, 59,
            tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
        )
        sunset = datetime.datetime(
            2024, 6, 21, 19, 13,
            tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
        )
        mock_calc.get_times.return_value = MagicMock(
            sunrise=sunrise, sunset=sunset
        )
        mocker.patch("solaris.cli.SolarCalculator", return_value=mock_calc)
        install = mocker.patch("solaris.cli.systemd_manager.install_units")
        enable = mocker.patch("solaris.cli.systemd_manager.enable")

        cli._handle_install_timer(SolarisConfig(schedule_mode=SCHEDULE_MODE_SOLAR))
        install.assert_called_once()
        enable.assert_called_once()

    def test_time_mode_writes_time_based_timer(self, mocker, capsys):
        mocker.patch("solaris.cli.systemd_manager.UNIT_DIR")
        mocker.patch("solaris.cli.systemd_manager.update_timer_time_based")
        mocker.patch("solaris.cli.systemd_manager.enable")

        cfg = SolarisConfig(schedule_mode=SCHEDULE_MODE_TIME)
        cli._handle_install_timer(cfg)
        out = capsys.readouterr().out
        assert "time-based" in out.lower() or "Light at" in out

    def test_manual_mode_skips(self, mocker, capsys):
        install = mocker.patch("solaris.cli.systemd_manager.install_units")
        cfg = SolarisConfig(schedule_mode=SCHEDULE_MODE_MANUAL)
        cli._handle_install_timer(cfg)
        install.assert_not_called()
        out = capsys.readouterr().out
        assert "Manual" in out

    def test_solar_failure_exits_nonzero(self, mocker):
        mock_calc = MagicMock()
        mock_calc.get_times.side_effect = Exception("astral broke")
        mocker.patch("solaris.cli.SolarCalculator", return_value=mock_calc)

        with pytest.raises(SystemExit) as exc:
            cli._handle_install_timer(SolarisConfig(schedule_mode=SCHEDULE_MODE_SOLAR))
        assert exc.value.code == 1


class TestHandleUpdateTimer:
    def test_solar_mode_updates(self, mocker):
        mock_calc = MagicMock()
        mock_calc.get_times.return_value = MagicMock(
            sunrise=datetime.datetime.now(datetime.timezone.utc),
            sunset=datetime.datetime.now(datetime.timezone.utc),
        )
        mocker.patch("solaris.cli.SolarCalculator", return_value=mock_calc)
        update = mocker.patch("solaris.cli.systemd_manager.update_timer")

        cli._handle_update_timer(SolarisConfig(schedule_mode=SCHEDULE_MODE_SOLAR))
        update.assert_called_once()

    def test_time_mode_updates_time_based(self, mocker):
        update = mocker.patch(
            "solaris.cli.systemd_manager.update_timer_time_based"
        )
        cli._handle_update_timer(SolarisConfig(schedule_mode=SCHEDULE_MODE_TIME))
        update.assert_called_once()

    def test_manual_mode_skips(self, mocker, capsys):
        update = mocker.patch("solaris.cli.systemd_manager.update_timer")
        cli._handle_update_timer(SolarisConfig(schedule_mode=SCHEDULE_MODE_MANUAL))
        update.assert_not_called()
        assert "Manual" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_verbose_sets_debug(self, mocker):
        basic = mocker.patch("solaris.cli.logging.basicConfig")
        cli._configure_logging(verbose=True)
        kwargs = basic.call_args.kwargs
        import logging
        assert kwargs["level"] == logging.DEBUG

    def test_default_sets_info(self, mocker):
        basic = mocker.patch("solaris.cli.logging.basicConfig")
        cli._configure_logging(verbose=False)
        kwargs = basic.call_args.kwargs
        import logging
        assert kwargs["level"] == logging.INFO
