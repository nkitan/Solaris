"""Solaris Dark Style Watcher.

Listens to the GNOME org.gnome.desktop.interface color-scheme GSettings key
— the same key toggled by the "Dark Style" button in the GNOME quick-settings
panel — and immediately applies the full Solaris theme stack whenever it changes.

This module is designed to run as a long-lived systemd user service
(solaris-watcher.service).  It uses Gio.Settings directly (not gsettings
subprocess) because we are READING the system schema, not the optional
user-theme schema, so the schema is always present.
"""

from __future__ import annotations

import logging
import signal
import sys

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib

from solaris import config as config_module
from solaris import firefox, theme_engine

logger = logging.getLogger(__name__)

_INTERFACE_SCHEMA = "org.gnome.desktop.interface"
_COLOR_SCHEME_KEY = "color-scheme"


class DarkStyleWatcher:
    """Watches org.gnome.desktop.interface color-scheme and syncs Solaris themes.

    When the GNOME "Dark Style" quick-settings toggle is flipped (in either
    direction), this watcher immediately applies:
      - GTK theme via gsettings
      - GNOME Shell theme via gsettings (if User Themes extension is enabled)
      - Firefox userChrome.css patch (if firefox_integration is True)

    The watcher reloads config from disk on every change, so updates made
    via the GUI or CLI while the watcher is running are always respected.
    """

    def __init__(self) -> None:
        self._settings = Gio.Settings(schema=_INTERFACE_SCHEMA)
        self._main_loop = GLib.MainLoop()
        self._handler_id: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Sync themes immediately, then block until a stop signal is received.

        Applies the current color-scheme theme on startup so the watcher is
        always consistent even if the toggle changed while it was stopped.
        Handles SIGTERM (sent by systemd on service stop) and SIGINT gracefully.
        """
        logger.info("Solaris Dark Style Watcher starting.")

        # Apply current state immediately so we're always in sync.
        self._sync_from_settings()

        # Subscribe to future changes.
        self._handler_id = self._settings.connect(
            f"changed::{_COLOR_SCHEME_KEY}",
            self._on_color_scheme_changed,
        )
        logger.info(
            "Watching %s:%s for changes. Send SIGTERM to stop.",
            _INTERFACE_SCHEMA,
            _COLOR_SCHEME_KEY,
        )

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._main_loop.run()

    def stop(self) -> None:
        """Disconnect from GSettings and stop the main loop."""
        if self._handler_id is not None:
            self._settings.disconnect(self._handler_id)
            self._handler_id = None

        if self._main_loop.is_running():
            self._main_loop.quit()

        logger.info("Solaris Dark Style Watcher stopped.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_signal(self, signum: int, _frame) -> None:
        """Respond to SIGTERM / SIGINT by gracefully stopping the loop."""
        logger.info("Received signal %d — stopping watcher.", signum)
        # Quit from within GLib main loop context to avoid threading issues.
        GLib.idle_add(self.stop)

    def _on_color_scheme_changed(
        self, settings: Gio.Settings, key: str
    ) -> None:
        """Called by GLib when color-scheme changes.

        Args:
            settings: The Gio.Settings object that emitted the signal.
            key:      The key that changed (always "color-scheme" here).
        """
        logger.info("color-scheme changed — syncing themes.")
        self._sync_from_settings()

    def _sync_from_settings(self) -> None:
        """Read the current color-scheme value and apply the matching theme stack.

        Reloads config from disk on every call so the watcher picks up any
        theme changes made via the GUI or CLI without needing a restart.
        """
        current_value = self._settings.get_string(_COLOR_SCHEME_KEY)
        logger.debug("color-scheme = %r", current_value)

        # "prefer-dark" → dark; everything else ("prefer-light", "default") → light
        mode = "dark" if current_value == "prefer-dark" else "light"

        cfg = config_module.load()
        _apply_mode(mode, cfg)


# ---------------------------------------------------------------------------
# Module-level helper (shared with CLI --watch handler)
# ---------------------------------------------------------------------------

def _apply_mode(mode: str, cfg: config_module.SolarisConfig) -> None:
    """Apply GTK, Shell, and Firefox themes for the given mode.

    Args:
        mode: "light" or "dark".
        cfg:  The loaded SolarisConfig providing theme names.
    """
    if mode == "dark":
        theme_engine.apply_dark(cfg)
    else:
        theme_engine.apply_light(cfg)

    if cfg.firefox_integration:
        firefox.apply_theme(mode)

    logger.info("Theme stack applied: mode=%s", mode)
