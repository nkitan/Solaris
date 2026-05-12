"""Solaris status dashboard page.

An Adw.PreferencesPage that shows:
  - Current light/dark mode with a sun/moon icon
  - Manual override toggle
  - Live countdown to the next solar transition
  - Apply Now button
  - systemd timer enable/disable control
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from solaris import config as config_module
from solaris import firefox, systemd_manager, theme_engine
from solaris.solar import SolarCalculator

logger = logging.getLogger(__name__)

_ICON_LIGHT = "weather-clear-symbolic"
_ICON_DARK = "weather-clear-night-symbolic"


class StatusPage(Adw.PreferencesPage):
    """Dashboard showing the current theme state and solar countdown."""

    def __init__(self, cfg: config_module.SolarisConfig, **kwargs) -> None:
        super().__init__(**kwargs)

        self._cfg = cfg
        self._calculator = SolarCalculator(cfg.latitude, cfg.longitude)
        self._countdown_timer_id: int | None = None

        self.set_icon_name("preferences-desktop-display-symbolic")
        self.set_title("Status")

        self._build_status_group()
        self._build_controls_group()
        self._build_timer_group()

        # Start the live countdown.
        self._update_countdown()
        self._countdown_timer_id = GLib.timeout_add_seconds(60, self._update_countdown)

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_status_group(self) -> None:
        """Build the current mode display group."""
        group = Adw.PreferencesGroup()
        group.set_title("Current State")
        self.add(group)

        # Mode row — icon + label
        self._mode_row = Adw.ActionRow()
        self._mode_row.set_title("Theme Mode")
        self._mode_icon = Gtk.Image()
        self._mode_icon.set_pixel_size(32)
        self._mode_row.add_prefix(self._mode_icon)
        self._mode_label = Gtk.Label()
        self._mode_label.add_css_class("dim-label")
        self._mode_row.add_suffix(self._mode_label)
        group.add(self._mode_row)

        # Countdown row
        self._countdown_row = Adw.ActionRow()
        self._countdown_row.set_title("Next Transition")
        self._countdown_label = Gtk.Label()
        self._countdown_label.add_css_class("dim-label")
        self._countdown_row.add_suffix(self._countdown_label)
        group.add(self._countdown_row)

        self._refresh_mode_display()

    def _build_controls_group(self) -> None:
        """Build the manual override and apply-now controls."""
        group = Adw.PreferencesGroup()
        group.set_title("Controls")
        self.add(group)

        # Override toggle
        self._override_row = Adw.SwitchRow()
        self._override_row.set_title("Manual Override")
        self._override_row.set_subtitle("Disable automatic solar scheduling")
        self._override_row.set_active(self._cfg.override_mode is not None)
        self._override_row.connect("notify::active", self._on_override_toggled)
        group.add(self._override_row)

        # Override mode dropdown (only visible when override is active)
        override_modes = Gtk.StringList()
        override_modes.append("Light")
        override_modes.append("Dark")

        self._override_mode_row = Adw.ComboRow()
        self._override_mode_row.set_title("Override Mode")
        self._override_mode_row.set_model(override_modes)
        self._override_mode_row.set_visible(self._cfg.override_mode is not None)
        self._override_mode_row.set_selected(
            1 if self._cfg.override_mode == "dark" else 0
        )
        self._override_mode_row.connect("notify::selected", self._on_override_mode_changed)
        group.add(self._override_mode_row)

        # Apply Now button row
        apply_row = Adw.ActionRow()
        apply_row.set_title("Apply Theme Now")
        apply_row.set_subtitle("Immediately apply the current mode")

        self._apply_button = Gtk.Button(label="Apply Now")
        self._apply_button.add_css_class("suggested-action")
        self._apply_button.set_valign(Gtk.Align.CENTER)
        self._apply_button.connect("clicked", self._on_apply_clicked)
        apply_row.add_suffix(self._apply_button)
        group.add(apply_row)

    def _build_timer_group(self) -> None:
        """Build the systemd timer status and toggle controls."""
        group = Adw.PreferencesGroup()
        group.set_title("Automation")
        self.add(group)

        self._timer_row = Adw.ActionRow()
        self._timer_row.set_title("Systemd Timer")

        self._timer_status_label = Gtk.Label()
        self._timer_status_label.add_css_class("dim-label")
        self._timer_row.add_suffix(self._timer_status_label)

        self._timer_button = Gtk.Button()
        self._timer_button.set_valign(Gtk.Align.CENTER)
        self._timer_button.connect("clicked", self._on_timer_toggled)
        self._timer_row.add_suffix(self._timer_button)

        group.add(self._timer_row)
        self._refresh_timer_display()

    # ------------------------------------------------------------------
    # State refresh helpers
    # ------------------------------------------------------------------

    def _refresh_mode_display(self) -> None:
        """Update the mode icon and label to match the current gsettings state."""
        mode = theme_engine.get_current_mode()
        if mode == "light":
            self._mode_icon.set_from_icon_name(_ICON_LIGHT)
            self._mode_label.set_text("☀️  Light Mode")
        elif mode == "dark":
            self._mode_icon.set_from_icon_name(_ICON_DARK)
            self._mode_label.set_text("🌙  Dark Mode")
        else:
            self._mode_icon.set_from_icon_name("dialog-question-symbolic")
            self._mode_label.set_text("Unknown")

    def _refresh_timer_display(self) -> None:
        """Update the timer status label and button text."""
        active = systemd_manager.is_active()
        enabled = systemd_manager.is_enabled()

        if active:
            self._timer_status_label.set_text("Active ✅")
            self._timer_button.set_label("Disable")
            self._timer_button.remove_css_class("suggested-action")
            self._timer_button.add_css_class("destructive-action")
        else:
            self._timer_status_label.set_text("Inactive ❌")
            self._timer_button.set_label("Enable")
            self._timer_button.remove_css_class("destructive-action")
            self._timer_button.add_css_class("suggested-action")

        _ = enabled  # stored for future tooltip use

    def _update_countdown(self) -> bool:
        """Update the countdown label. Called by GLib timer every 60 seconds.

        Returns:
            GLib.SOURCE_CONTINUE (True) to keep the timer running.
        """
        try:
            countdown_text = self._calculator.format_countdown()
        except Exception as exc:
            logger.warning("Countdown update failed: %s", exc)
            countdown_text = "Unavailable"

        self._countdown_label.set_text(countdown_text)
        self._refresh_mode_display()
        return GLib.SOURCE_CONTINUE

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_override_toggled(self, switch_row: Adw.SwitchRow, _param) -> None:
        """Show/hide the override mode dropdown when the override switch changes."""
        is_active = switch_row.get_active()
        self._override_mode_row.set_visible(is_active)

        if is_active:
            selected = self._override_mode_row.get_selected()
            self._cfg.override_mode = "dark" if selected == 1 else "light"
        else:
            self._cfg.override_mode = None

        config_module.save(self._cfg)

    def _on_override_mode_changed(self, combo_row: Adw.ComboRow, _param) -> None:
        """Update override_mode in config when the dropdown selection changes."""
        if not self._override_row.get_active():
            return
        selected = combo_row.get_selected()
        self._cfg.override_mode = "dark" if selected == 1 else "light"
        config_module.save(self._cfg)

    def _on_apply_clicked(self, _button: Gtk.Button) -> None:
        """Apply the current mode (respecting override) immediately."""
        if self._cfg.override_mode == "dark":
            mode = "dark"
        elif self._cfg.override_mode == "light":
            mode = "light"
        else:
            mode = self._calculator.get_current_mode()

        if mode == "light":
            theme_engine.apply_light(self._cfg)
        else:
            theme_engine.apply_dark(self._cfg)

        if self._cfg.firefox_integration:
            firefox.apply_theme(mode)

        self._refresh_mode_display()

        # Show a brief success toast.
        toast = Adw.Toast(title=f"✓ {mode.capitalize()} theme applied")
        toast.set_timeout(2)
        # Walk up to the window to show the toast.
        parent = self.get_root()
        if isinstance(parent, Adw.ApplicationWindow):
            overlay = parent.get_content()
            if isinstance(overlay, Adw.ToastOverlay):
                overlay.add_toast(toast)

    def _on_timer_toggled(self, _button: Gtk.Button) -> None:
        """Enable or disable the systemd timer based on current state."""
        if systemd_manager.is_active():
            systemd_manager.disable()
        else:
            systemd_manager.enable()
        self._refresh_timer_display()

    def cleanup(self) -> None:
        """Cancel the GLib countdown timer. Call before destroying the page."""
        if self._countdown_timer_id is not None:
            GLib.source_remove(self._countdown_timer_id)
            self._countdown_timer_id = None
