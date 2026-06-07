"""Tests for solaris.watcher — Dark Style watcher logic (no real GLib loop)."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock

import pytest

from solaris import watcher
from solaris.config import SolarisConfig


@pytest.fixture
def mock_gio_settings(mocker):
    """Stub Gio.Settings so the watcher can be instantiated without a real schema."""
    fake_settings = MagicMock()
    mocker.patch(
        "solaris.watcher.Gio.Settings", return_value=fake_settings
    )
    return fake_settings


@pytest.fixture
def mock_main_loop(mocker):
    """Stub GLib.MainLoop so the watcher doesn't actually block."""
    fake_loop = MagicMock()
    fake_loop.is_running.return_value = False
    mocker.patch("solaris.watcher.GLib.MainLoop", return_value=fake_loop)
    return fake_loop


# ---------------------------------------------------------------------------
# _apply_mode
# ---------------------------------------------------------------------------


class TestApplyMode:
    def test_dark_calls_theme_engine_apply_dark(self, mocker):
        dark = mocker.patch("solaris.watcher.theme_engine.apply_dark")
        light = mocker.patch("solaris.watcher.theme_engine.apply_light")
        mocker.patch("solaris.watcher.firefox.apply_theme")
        mocker.patch("solaris.watcher.ghostty.apply_theme")

        cfg = SolarisConfig()
        watcher._apply_mode("dark", cfg)
        dark.assert_called_once_with(cfg)
        light.assert_not_called()

    def test_light_calls_theme_engine_apply_light(self, mocker):
        dark = mocker.patch("solaris.watcher.theme_engine.apply_dark")
        light = mocker.patch("solaris.watcher.theme_engine.apply_light")
        mocker.patch("solaris.watcher.firefox.apply_theme")
        mocker.patch("solaris.watcher.ghostty.apply_theme")

        cfg = SolarisConfig()
        watcher._apply_mode("light", cfg)
        light.assert_called_once_with(cfg)
        dark.assert_not_called()

    def test_firefox_called_when_integration_enabled(self, mocker):
        mocker.patch("solaris.watcher.theme_engine.apply_light")
        ff = mocker.patch("solaris.watcher.firefox.apply_theme")
        mocker.patch("solaris.watcher.ghostty.apply_theme")

        cfg = SolarisConfig(firefox_integration=True)
        watcher._apply_mode("light", cfg)
        ff.assert_called_once_with("light")

    def test_firefox_skipped_when_disabled(self, mocker):
        mocker.patch("solaris.watcher.theme_engine.apply_light")
        ff = mocker.patch("solaris.watcher.firefox.apply_theme")
        mocker.patch("solaris.watcher.ghostty.apply_theme")

        cfg = SolarisConfig(firefox_integration=False)
        watcher._apply_mode("light", cfg)
        ff.assert_not_called()

    def test_ghostty_called_when_integration_enabled(self, mocker):
        mocker.patch("solaris.watcher.theme_engine.apply_light")
        mocker.patch("solaris.watcher.firefox.apply_theme")
        gh = mocker.patch("solaris.watcher.ghostty.apply_theme")

        cfg = SolarisConfig(ghostty_integration=True)
        watcher._apply_mode("light", cfg)
        gh.assert_called_once_with("light", cfg)

    def test_ghostty_skipped_when_disabled(self, mocker):
        mocker.patch("solaris.watcher.theme_engine.apply_light")
        mocker.patch("solaris.watcher.firefox.apply_theme")
        gh = mocker.patch("solaris.watcher.ghostty.apply_theme")

        cfg = SolarisConfig(ghostty_integration=False)
        watcher._apply_mode("light", cfg)
        gh.assert_not_called()


# ---------------------------------------------------------------------------
# DarkStyleWatcher — init / sync / stop
# ---------------------------------------------------------------------------


class TestDarkStyleWatcherInit:
    def test_init_creates_settings_object(self, mock_gio_settings, mock_main_loop):
        w = watcher.DarkStyleWatcher()
        assert w._settings is mock_gio_settings
        assert w._handler_id is None
        assert w._last_applied_mode is None


class TestSyncFromSettings:
    def test_applies_dark_when_color_scheme_is_prefer_dark(
        self, mock_gio_settings, mock_main_loop, mocker
    ):
        mock_gio_settings.get_string.return_value = "prefer-dark"
        mocker.patch(
            "solaris.watcher.config_module.load", return_value=SolarisConfig()
        )
        apply = mocker.patch("solaris.watcher._apply_mode")

        w = watcher.DarkStyleWatcher()
        w._sync_from_settings()
        apply.assert_called_once_with("dark", mocker.ANY)

    def test_applies_light_when_color_scheme_is_prefer_light(
        self, mock_gio_settings, mock_main_loop, mocker
    ):
        mock_gio_settings.get_string.return_value = "prefer-light"
        mocker.patch(
            "solaris.watcher.config_module.load", return_value=SolarisConfig()
        )
        apply = mocker.patch("solaris.watcher._apply_mode")

        w = watcher.DarkStyleWatcher()
        w._sync_from_settings()
        apply.assert_called_once_with("light", mocker.ANY)

    def test_default_treated_as_light(
        self, mock_gio_settings, mock_main_loop, mocker
    ):
        mock_gio_settings.get_string.return_value = "default"
        mocker.patch(
            "solaris.watcher.config_module.load", return_value=SolarisConfig()
        )
        apply = mocker.patch("solaris.watcher._apply_mode")

        w = watcher.DarkStyleWatcher()
        w._sync_from_settings()
        apply.assert_called_once_with("light", mocker.ANY)

    def test_skips_redundant_apply(
        self, mock_gio_settings, mock_main_loop, mocker
    ):
        mock_gio_settings.get_string.return_value = "prefer-dark"
        mocker.patch(
            "solaris.watcher.config_module.load", return_value=SolarisConfig()
        )
        apply = mocker.patch("solaris.watcher._apply_mode")

        w = watcher.DarkStyleWatcher()
        w._sync_from_settings()
        w._sync_from_settings()  # second call should be skipped
        assert apply.call_count == 1


class TestWatcherStop:
    def test_stop_disconnects_and_quits(
        self, mock_gio_settings, mock_main_loop
    ):
        w = watcher.DarkStyleWatcher()
        w._handler_id = 42
        mock_main_loop.is_running.return_value = True

        w.stop()
        mock_gio_settings.disconnect.assert_called_once_with(42)
        mock_main_loop.quit.assert_called_once()
        assert w._handler_id is None

    def test_stop_is_idempotent(self, mock_gio_settings, mock_main_loop):
        w = watcher.DarkStyleWatcher()
        w.stop()
        w.stop()
        # Should not raise.


class TestColorSchemeChangedSignal:
    def test_signal_triggers_sync(
        self, mock_gio_settings, mock_main_loop, mocker
    ):
        mock_gio_settings.get_string.return_value = "prefer-dark"
        mocker.patch(
            "solaris.watcher.config_module.load", return_value=SolarisConfig()
        )
        apply = mocker.patch("solaris.watcher._apply_mode")

        w = watcher.DarkStyleWatcher()
        w._on_color_scheme_changed(mock_gio_settings, "color-scheme")
        apply.assert_called_once()


class TestSignalHandler:
    def test_signal_handler_schedules_stop(
        self, mock_gio_settings, mock_main_loop, mocker
    ):
        idle_add = mocker.patch("solaris.watcher.GLib.idle_add")

        w = watcher.DarkStyleWatcher()
        w._handle_signal(signal.SIGTERM, None)
        idle_add.assert_called_once_with(w.stop)
