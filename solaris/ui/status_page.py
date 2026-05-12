"""Solaris status dashboard page.

An Adw.PreferencesPage that shows:
  - Current light/dark mode (mirrors the GNOME "Dark Style" quick-settings toggle)
  - Three-way schedule mode selector: Solar / Manual / Time-Based
  - Contextual sub-rows for each mode
  - Live countdown (solar mode only)
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
from solaris.config import (
    SCHEDULE_MODE_MANUAL,
    SCHEDULE_MODE_SOLAR,
    SCHEDULE_MODE_TIME,
)
from solaris import firefox, systemd_manager, theme_engine
from solaris.solar import SolarCalculator

logger = logging.getLogger(__name__)

_ICON_LIGHT = "weather-clear-symbolic"
_ICON_DARK = "weather-clear-night-symbolic"

# Indices in the schedule mode ComboRow — must match SCHEDULE_LABELS order.
_IDX_SOLAR = 0
_IDX_MANUAL = 1
_IDX_TIME = 2
_SCHEDULE_LABELS = ("Solar (Sunrise / Sunset)", "Manual", "Time-Based")
_SCHEDULE_MODE_FROM_IDX = {
    _IDX_SOLAR: SCHEDULE_MODE_SOLAR,
    _IDX_MANUAL: SCHEDULE_MODE_MANUAL,
    _IDX_TIME: SCHEDULE_MODE_TIME,
}
_IDX_FROM_SCHEDULE_MODE = {v: k for k, v in _SCHEDULE_MODE_FROM_IDX.items()}


class StatusPage(Adw.PreferencesPage):
    """Dashboard showing the current theme state and schedule controls."""

    def __init__(self, cfg: config_module.SolarisConfig, **kwargs) -> None:
        super().__init__(**kwargs)

        self._cfg = cfg
        self._calculator = SolarCalculator(cfg.latitude, cfg.longitude)
        self._countdown_timer_id: int | None = None

        self.set_icon_name("preferences-desktop-display-symbolic")
        self.set_title("Status")

        self._build_status_group()
        self._build_schedule_group()
        self._build_apply_group()
        self._build_timer_group()
        self._build_integration_group()

        # Start the live countdown.
        self._update_countdown()
        self._countdown_timer_id = GLib.timeout_add_seconds(60, self._update_countdown)

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_status_group(self) -> None:
        """Build the current mode display group (mirrors GNOME Dark Style toggle)."""
        group = Adw.PreferencesGroup()
        group.set_title("Current State")
        group.set_description(
            "Reflects the GNOME \u201cDark Style\u201d quick-settings toggle"
        )
        self.add(group)

        # Mode row — icon + label
        self._mode_row = Adw.ActionRow()
        self._mode_row.set_title("Active Mode")
        self._mode_icon = Gtk.Image()
        self._mode_icon.set_pixel_size(32)
        self._mode_row.add_prefix(self._mode_icon)
        self._mode_label = Gtk.Label()
        self._mode_label.add_css_class("dim-label")
        self._mode_row.add_suffix(self._mode_label)
        group.add(self._mode_row)

        # Countdown row — only meaningful in solar mode; hidden otherwise.
        self._countdown_row = Adw.ActionRow()
        self._countdown_row.set_title("Next Transition")
        self._countdown_label = Gtk.Label()
        self._countdown_label.add_css_class("dim-label")
        self._countdown_row.add_suffix(self._countdown_label)
        group.add(self._countdown_row)

        self._refresh_mode_display()

    def _build_schedule_group(self) -> None:
        """Build the three-way schedule mode selector with contextual sub-rows."""
        group = Adw.PreferencesGroup()
        group.set_title("Schedule")
        group.set_description("How Solaris decides when to switch modes")
        self.add(group)

        # ── Top-level mode selector ──────────────────────────────────────
        schedule_list = Gtk.StringList()
        for label in _SCHEDULE_LABELS:
            schedule_list.append(label)

        self._schedule_row = Adw.ComboRow()
        self._schedule_row.set_title("Scheduling Mode")
        self._schedule_row.set_model(schedule_list)
        self._schedule_row.set_selected(
            _IDX_FROM_SCHEDULE_MODE.get(self._cfg.schedule_mode, _IDX_SOLAR)
        )
        self._schedule_row.connect("notify::selected", self._on_schedule_mode_changed)
        group.add(self._schedule_row)

        # ── Manual sub-row (visible only in MANUAL mode) ─────────────────
        manual_choices = Gtk.StringList()
        manual_choices.append("Light")
        manual_choices.append("Dark")

        self._manual_mode_row = Adw.ComboRow()
        self._manual_mode_row.set_title("Always Use")
        self._manual_mode_row.set_subtitle(
            "The GNOME Dark Style toggle will be set to this mode"
        )
        self._manual_mode_row.set_model(manual_choices)
        self._manual_mode_row.set_selected(
            1 if self._cfg.manual_mode == "dark" else 0
        )
        self._manual_mode_row.connect("notify::selected", self._on_manual_mode_changed)
        group.add(self._manual_mode_row)

        # ── Time-based sub-rows (visible only in TIME mode) ──────────────
        self._time_light_row = Adw.EntryRow()
        self._time_light_row.set_title("Light Mode Start")
        self._time_light_row.set_tooltip_text("24-hour format, e.g. 07:00")
        self._time_light_row.set_text(self._cfg.time_light_start)
        self._time_light_row.connect("changed", self._on_time_entry_changed)
        group.add(self._time_light_row)

        self._time_dark_row = Adw.EntryRow()
        self._time_dark_row.set_title("Dark Mode Start")
        self._time_dark_row.set_tooltip_text("24-hour format, e.g. 20:00")
        self._time_dark_row.set_text(self._cfg.time_dark_start)
        self._time_dark_row.connect("changed", self._on_time_entry_changed)
        group.add(self._time_dark_row)

        # Apply initial visibility based on saved mode.
        self._refresh_schedule_subrows(self._cfg.schedule_mode)

    def _build_apply_group(self) -> None:
        """Build the Apply Now button row."""
        group = Adw.PreferencesGroup()
        group.set_title("Controls")
        self.add(group)

        apply_row = Adw.ActionRow()
        apply_row.set_title("Apply Theme Now")
        apply_row.set_subtitle(
            "Immediately apply the correct mode and update the Dark Style toggle"
        )

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
        self._timer_row.set_subtitle(
            "Automatically applies the theme at each scheduled transition"
        )

        self._timer_status_label = Gtk.Label()
        self._timer_status_label.add_css_class("dim-label")
        self._timer_row.add_suffix(self._timer_status_label)

        self._timer_button = Gtk.Button()
        self._timer_button.set_valign(Gtk.Align.CENTER)
        self._timer_button.connect("clicked", self._on_timer_toggled)
        self._timer_row.add_suffix(self._timer_button)

        group.add(self._timer_row)
        self._refresh_timer_display()

    def _build_integration_group(self) -> None:
        """Build the GNOME Integration settings group."""
        group = Adw.PreferencesGroup()
        group.set_title("GNOME Integration")
        self.add(group)

        self._follow_dark_style_row = Adw.SwitchRow()
        self._follow_dark_style_row.set_title("Follow GNOME Dark Style")
        self._follow_dark_style_row.set_subtitle(
            "Automatically apply Solaris themes when the GNOME quick-settings toggle changes"
        )
        self._follow_dark_style_row.set_active(self._cfg.follow_dark_style)
        self._follow_dark_style_row.connect(
            "notify::active", self._on_follow_dark_style_toggled
        )
        group.add(self._follow_dark_style_row)

    # ------------------------------------------------------------------
    # State refresh helpers
    # ------------------------------------------------------------------

    def _refresh_mode_display(self) -> None:
        """Update the mode icon and label to match the current gsettings state.

        This reflects whatever the GNOME 'Dark Style' quick-settings toggle shows.
        """
        mode = theme_engine.get_current_mode()
        if mode == "light":
            self._mode_icon.set_from_icon_name(_ICON_LIGHT)
            self._mode_label.set_text("\u2600\ufe0f  Light Mode")
        elif mode == "dark":
            self._mode_icon.set_from_icon_name(_ICON_DARK)
            self._mode_label.set_text("\U0001f319  Dark Mode")
        else:
            self._mode_icon.set_from_icon_name("dialog-question-symbolic")
            self._mode_label.set_text("Unknown")

    def _refresh_schedule_subrows(self, schedule_mode: str) -> None:
        """Show/hide contextual sub-rows based on the active schedule mode."""
        is_solar = schedule_mode == SCHEDULE_MODE_SOLAR
        is_manual = schedule_mode == SCHEDULE_MODE_MANUAL
        is_time = schedule_mode == SCHEDULE_MODE_TIME

        self._countdown_row.set_visible(is_solar)
        self._manual_mode_row.set_visible(is_manual)
        self._time_light_row.set_visible(is_time)
        self._time_dark_row.set_visible(is_time)

    def _refresh_timer_display(self) -> None:
        """Update the timer status label and button text."""
        active = systemd_manager.is_active()
        enabled = systemd_manager.is_enabled()

        if active:
            self._timer_status_label.set_text("Active \u2705")
            self._timer_button.set_label("Disable")
            self._timer_button.remove_css_class("suggested-action")
            self._timer_button.add_css_class("destructive-action")
        else:
            self._timer_status_label.set_text("Inactive \u274c")
            self._timer_button.set_label("Enable")
            self._timer_button.remove_css_class("destructive-action")
            self._timer_button.add_css_class("suggested-action")

        _ = enabled  # reserved for tooltip

    def _update_countdown(self) -> bool:
        """Update the countdown label. Called by GLib timer every 60 seconds.

        Returns:
            GLib.SOURCE_CONTINUE to keep the timer alive.
        """
        # Recreate the calculator in case coordinates changed since init.
        try:
            calculator = SolarCalculator(self._cfg.latitude, self._cfg.longitude)
            countdown_text = calculator.format_countdown()
        except Exception as exc:
            logger.warning("Countdown update failed: %s", exc)
            countdown_text = "Unavailable"

        self._countdown_label.set_text(countdown_text)
        self._refresh_mode_display()
        return GLib.SOURCE_CONTINUE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_current_mode(self) -> str:
        """Determine the mode to apply based on the active schedule_mode.

        Returns:
            "light" or "dark".
        """
        schedule_mode = self._cfg.schedule_mode

        if schedule_mode == SCHEDULE_MODE_MANUAL:
            return self._cfg.manual_mode

        if schedule_mode == SCHEDULE_MODE_TIME:
            import datetime

            def _parse(hhmm: str) -> datetime.time:
                h, m = hhmm.split(":")
                return datetime.time(int(h), int(m))

            now = datetime.datetime.now().time()
            light_start = _parse(self._cfg.time_light_start)
            dark_start = _parse(self._cfg.time_dark_start)

            if light_start < dark_start:
                return "light" if light_start <= now < dark_start else "dark"
            else:
                return "dark" if dark_start <= now < light_start else "light"

        # SOLAR (default)
        try:
            calculator = SolarCalculator(self._cfg.latitude, self._cfg.longitude)
            return calculator.get_current_mode()
        except Exception as exc:
            logger.warning("Solar mode calculation failed: %s — defaulting to dark", exc)
            return "dark"

    def _show_toast(self, message: str, timeout: int = 2) -> None:
        """Display a brief Adw.Toast in the parent window's overlay."""
        toast = Adw.Toast(title=message)
        toast.set_timeout(timeout)
        parent = self.get_root()
        if isinstance(parent, Adw.ApplicationWindow):
            overlay = parent.get_content()
            if isinstance(overlay, Adw.ToastOverlay):
                overlay.add_toast(toast)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_schedule_mode_changed(self, combo_row: Adw.ComboRow, _param) -> None:
        """Persist the new schedule mode and update visible sub-rows."""
        idx = combo_row.get_selected()
        new_mode = _SCHEDULE_MODE_FROM_IDX.get(idx, SCHEDULE_MODE_SOLAR)

        self._cfg.schedule_mode = new_mode
        config_module.save(self._cfg)
        self._refresh_schedule_subrows(new_mode)

        # In solar mode, refresh countdown immediately.
        if new_mode == SCHEDULE_MODE_SOLAR:
            self._update_countdown()

    def _on_manual_mode_changed(self, combo_row: Adw.ComboRow, _param) -> None:
        """Persist manual_mode when the Light/Dark dropdown changes."""
        selected = combo_row.get_selected()
        self._cfg.manual_mode = "dark" if selected == 1 else "light"
        config_module.save(self._cfg)

    def _on_time_entry_changed(self, _entry_row: Adw.EntryRow) -> None:
        """Validate and persist both time inputs when either changes."""
        import re

        light_text = self._time_light_row.get_text().strip()
        dark_text = self._time_dark_row.get_text().strip()
        hhmm_re = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

        if not (hhmm_re.match(light_text) and hhmm_re.match(dark_text)):
            return  # don't save invalid inputs

        self._cfg.time_light_start = light_text
        self._cfg.time_dark_start = dark_text
        config_module.save(self._cfg)

    def _on_apply_clicked(self, _button: Gtk.Button) -> None:
        """Apply the correct mode for the current schedule, patching color-scheme and Firefox."""
        mode = self._resolve_current_mode()

        if mode == "light":
            theme_engine.apply_light(self._cfg)
        else:
            theme_engine.apply_dark(self._cfg)

        if self._cfg.firefox_integration:
            firefox.apply_theme(mode)

        self._refresh_mode_display()
        self._show_toast(f"\u2713 {mode.capitalize()} theme applied")

    def _on_timer_toggled(self, _button: Gtk.Button) -> None:
        """Enable or disable the systemd timer based on current state."""
        if systemd_manager.is_active():
            systemd_manager.disable()
        else:
            # Install correct timer type first, then enable.
            if self._cfg.schedule_mode == SCHEDULE_MODE_TIME:
                systemd_manager.update_timer_time_based(
                    self._cfg.time_light_start, self._cfg.time_dark_start
                )
            elif self._cfg.schedule_mode == SCHEDULE_MODE_SOLAR:
                try:
                    calculator = SolarCalculator(
                        self._cfg.latitude, self._cfg.longitude
                    )
                    today_times = calculator.get_times()
                    systemd_manager.update_timer(
                        today_times.sunrise, today_times.sunset
                    )
                except Exception as exc:
                    logger.warning("Could not update solar timer before enabling: %s", exc)
            systemd_manager.enable()

        self._refresh_timer_display()

    def _on_follow_dark_style_toggled(
        self, switch_row: Adw.SwitchRow, _param
    ) -> None:
        """Enable or disable the Dark Style watcher service."""
        is_active = switch_row.get_active()
        self._cfg.follow_dark_style = is_active
        config_module.save(self._cfg)

        if is_active:
            systemd_manager.enable_watcher()
        else:
            systemd_manager.disable_watcher()

    def cleanup(self) -> None:
        """Cancel the GLib countdown timer. Call before destroying the page."""
        if self._countdown_timer_id is not None:
            GLib.source_remove(self._countdown_timer_id)
            self._countdown_timer_id = None
