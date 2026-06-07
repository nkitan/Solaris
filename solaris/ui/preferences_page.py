"""Solaris preferences page.

An Adw.PreferencesPage containing three preference groups:
  - Theme: light/dark GTK and Shell theme dropdowns
  - Location: latitude/longitude inputs with GeoClue2 detect button
  - Firefox: integration toggle and detected profile display
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from solaris import config as config_module
from solaris import firefox, ghostty, theme_engine
from solaris.solar import SolarCalculator

logger = logging.getLogger(__name__)


class PreferencesPage(Adw.PreferencesPage):
    """Settings page for themes, location, and Firefox integration."""

    def __init__(self, cfg: config_module.SolarisConfig, **kwargs) -> None:
        super().__init__(**kwargs)

        self._cfg = cfg
        self._geoclue_timeout_id: int | None = None

        self.set_icon_name("emblem-system-symbolic")
        self.set_title("Preferences")

        self._build_theme_group()
        self._build_location_group()
        self._build_firefox_group()
        self._build_ghostty_group()

    # ------------------------------------------------------------------
    # Group builders
    # ------------------------------------------------------------------

    def _build_theme_group(self) -> None:
        """Build the theme selection group with four Adw.ComboRow dropdowns."""
        group = Adw.PreferencesGroup()
        group.set_title("Themes")
        group.set_description("GTK and GNOME Shell themes for each mode")
        self.add(group)

        all_themes = theme_engine.scan_themes()  # Colloid variants by default
        if not all_themes:
            all_themes = ["(no themes found)"]

        theme_list = Gtk.StringList()
        for theme_name in all_themes:
            theme_list.append(theme_name)

        def _make_combo(title: str, subtitle: str, current_value: str) -> Adw.ComboRow:
            row = Adw.ComboRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_model(theme_list)
            # Select the index matching the saved value, default to 0.
            try:
                idx = all_themes.index(current_value)
            except ValueError:
                idx = 0
            row.set_selected(idx)
            return row

        self._light_gtk_row = _make_combo(
            "Light GTK Theme", "Applied during daytime", self._cfg.light_gtk_theme
        )
        self._light_gtk_row.connect("notify::selected", self._on_theme_changed)
        group.add(self._light_gtk_row)

        self._dark_gtk_row = _make_combo(
            "Dark GTK Theme", "Applied during night", self._cfg.dark_gtk_theme
        )
        self._dark_gtk_row.connect("notify::selected", self._on_theme_changed)
        group.add(self._dark_gtk_row)

        self._light_shell_row = _make_combo(
            "Light Shell Theme", "GNOME Shell — daytime (requires User Themes extension)",
            self._cfg.light_shell_theme,
        )
        self._light_shell_row.connect("notify::selected", self._on_theme_changed)
        group.add(self._light_shell_row)

        self._dark_shell_row = _make_combo(
            "Dark Shell Theme", "GNOME Shell — night (requires User Themes extension)",
            self._cfg.dark_shell_theme,
        )
        self._dark_shell_row.connect("notify::selected", self._on_theme_changed)
        group.add(self._dark_shell_row)

        self._all_themes = all_themes  # keep reference for index lookups

    def _build_location_group(self) -> None:
        """Build the location group with latitude/longitude inputs and GeoClue button."""
        group = Adw.PreferencesGroup()
        group.set_title("Location")
        group.set_description("Used to calculate local sunrise and sunset times")
        self.add(group)

        self._lat_row = Adw.EntryRow()
        self._lat_row.set_title("Latitude")
        self._lat_row.set_text(str(self._cfg.latitude))
        self._lat_row.connect("changed", self._on_location_changed)
        group.add(self._lat_row)

        self._lon_row = Adw.EntryRow()
        self._lon_row.set_title("Longitude")
        self._lon_row.set_text(str(self._cfg.longitude))
        self._lon_row.connect("changed", self._on_location_changed)
        group.add(self._lon_row)

        # Detect Location button row
        detect_row = Adw.ActionRow()
        detect_row.set_title("Detect Location")
        detect_row.set_subtitle("Uses GNOME Location Services (GeoClue2)")

        self._detect_button = Gtk.Button(label="Detect")
        self._detect_button.set_valign(Gtk.Align.CENTER)
        self._detect_button.connect("clicked", self._on_detect_location)
        detect_row.add_suffix(self._detect_button)
        group.add(detect_row)

        # Preview row — shows calculated sunrise/sunset for current coords
        self._solar_preview_row = Adw.ActionRow()
        self._solar_preview_row.set_title("Today's Sun Times")
        self._solar_preview_label = Gtk.Label()
        self._solar_preview_label.add_css_class("dim-label")
        self._solar_preview_row.add_suffix(self._solar_preview_label)
        group.add(self._solar_preview_row)

        self._refresh_solar_preview()

    def _build_firefox_group(self) -> None:
        """Build the Firefox integration group."""
        group = Adw.PreferencesGroup()
        group.set_title("Firefox")
        group.set_description("Patch userChrome.css with Solaris colour variables")
        self.add(group)

        self._firefox_switch_row = Adw.SwitchRow()
        self._firefox_switch_row.set_title("Firefox Integration")
        self._firefox_switch_row.set_subtitle(
            "Swap background and text colours in userChrome.css"
        )
        self._firefox_switch_row.set_active(self._cfg.firefox_integration)
        self._firefox_switch_row.connect("notify::active", self._on_firefox_toggled)
        group.add(self._firefox_switch_row)

        # Detected profile path (read-only display)
        profile_row = Adw.ActionRow()
        profile_row.set_title("Active Firefox Profile")

        self._profile_label = Gtk.Label()
        self._profile_label.add_css_class("dim-label")
        self._profile_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        self._profile_label.set_max_width_chars(40)

        profile_path = firefox.find_active_profile()
        if profile_path is not None:
            self._profile_label.set_text(str(profile_path))
        else:
            self._profile_label.set_text("Not found")

        profile_row.add_suffix(self._profile_label)
        group.add(profile_row)

    def _build_ghostty_group(self) -> None:
        """Build the Ghostty integration group."""
        group = Adw.PreferencesGroup()
        group.set_title("Ghostty")
        group.set_description("Patch Ghostty config with Solaris themes and reload on change")
        self.add(group)

        self._ghostty_switch_row = Adw.SwitchRow()
        self._ghostty_switch_row.set_title("Ghostty Integration")
        self._ghostty_switch_row.set_subtitle(
            "Apply themes to Ghostty and reload running terminals"
        )
        self._ghostty_switch_row.set_active(self._cfg.ghostty_integration)
        self._ghostty_switch_row.connect("notify::active", self._on_ghostty_toggled)
        group.add(self._ghostty_switch_row)

        all_ghostty_themes = ghostty.scan_themes()
        if not all_ghostty_themes:
            all_ghostty_themes = ["(no themes found)"]

        ghostty_theme_list = Gtk.StringList()
        for theme_name in all_ghostty_themes:
            ghostty_theme_list.append(theme_name)

        def _make_ghostty_combo(title: str, subtitle: str, current_value: str) -> Adw.ComboRow:
            row = Adw.ComboRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_model(ghostty_theme_list)
            try:
                idx = all_ghostty_themes.index(current_value)
            except ValueError:
                idx = 0
            row.set_selected(idx)
            return row

        self._light_ghostty_row = _make_ghostty_combo(
            "Light Ghostty Theme", "Applied during daytime", self._cfg.light_ghostty_theme
        )
        self._light_ghostty_row.connect("notify::selected", self._on_ghostty_theme_changed)
        group.add(self._light_ghostty_row)

        self._dark_ghostty_row = _make_ghostty_combo(
            "Dark Ghostty Theme", "Applied during night", self._cfg.dark_ghostty_theme
        )
        self._dark_ghostty_row.connect("notify::selected", self._on_ghostty_theme_changed)
        group.add(self._dark_ghostty_row)

        decor_list = Gtk.StringList()
        decors = ("auto", "none", "client", "server")
        for d in decors:
            decor_list.append(d)

        self._ghostty_decor_row = Adw.ComboRow()
        self._ghostty_decor_row.set_title("Window Decoration")
        self._ghostty_decor_row.set_subtitle("Preference for window titlebar style")
        self._ghostty_decor_row.set_model(decor_list)
        try:
            idx = decors.index(self._cfg.ghostty_window_decoration)
        except ValueError:
            idx = 0
        self._ghostty_decor_row.set_selected(idx)
        self._ghostty_decor_row.connect("notify::selected", self._on_ghostty_decoration_changed)
        group.add(self._ghostty_decor_row)

        self._all_ghostty_themes = all_ghostty_themes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_solar_preview(self) -> None:
        """Update the sunrise/sunset preview label for the current coordinates."""
        try:
            lat = float(self._lat_row.get_text())
            lon = float(self._lon_row.get_text())
            calculator = SolarCalculator(lat, lon)
            times = calculator.get_times()
            sunrise_str = times.sunrise.strftime("%H:%M")
            sunset_str = times.sunset.strftime("%H:%M")
            self._solar_preview_label.set_text(f"↑ {sunrise_str}  ↓ {sunset_str}")
        except (ValueError, Exception) as exc:
            logger.debug("Solar preview failed: %s", exc)
            self._solar_preview_label.set_text("—")

    def _save_theme_config(self) -> None:
        """Read all four combo rows and persist theme names to config."""
        themes = self._all_themes

        def _get_theme(row: Adw.ComboRow) -> str:
            idx = row.get_selected()
            return themes[idx] if idx < len(themes) else themes[0]

        self._cfg.light_gtk_theme = _get_theme(self._light_gtk_row)
        self._cfg.dark_gtk_theme = _get_theme(self._dark_gtk_row)
        self._cfg.light_shell_theme = _get_theme(self._light_shell_row)
        self._cfg.dark_shell_theme = _get_theme(self._dark_shell_row)
        config_module.save(self._cfg)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_theme_changed(self, _combo_row: Adw.ComboRow, _param) -> None:
        """Persist updated theme selections when any dropdown changes."""
        self._save_theme_config()

    def _on_location_changed(self, _entry_row: Adw.EntryRow) -> None:
        """Validate and save coordinates; refresh the solar preview."""
        try:
            lat = float(self._lat_row.get_text())
            lon = float(self._lon_row.get_text())
            config_module._validate_latitude(lat)
            config_module._validate_longitude(lon)
        except ValueError:
            # Don't save invalid coordinates — just skip.
            return

        self._cfg.latitude = lat
        self._cfg.longitude = lon
        config_module.save(self._cfg)
        self._refresh_solar_preview()

    def _on_firefox_toggled(self, switch_row: Adw.SwitchRow, _param) -> None:
        """Persist the Firefox integration toggle state."""
        self._cfg.firefox_integration = switch_row.get_active()
        config_module.save(self._cfg)

    def _on_ghostty_toggled(self, switch_row: Adw.SwitchRow, _param) -> None:
        """Persist the Ghostty integration toggle state."""
        self._cfg.ghostty_integration = switch_row.get_active()
        config_module.save(self._cfg)
        self._apply_ghostty_theme_if_active()

    def _on_ghostty_theme_changed(self, _combo_row: Adw.ComboRow, _param) -> None:
        """Persist updated Ghostty theme selections when any dropdown changes."""
        themes = self._all_ghostty_themes

        def _get_theme(row: Adw.ComboRow) -> str:
            idx = row.get_selected()
            return themes[idx] if idx < len(themes) else themes[0]

        self._cfg.light_ghostty_theme = _get_theme(self._light_ghostty_row)
        self._cfg.dark_ghostty_theme = _get_theme(self._dark_ghostty_row)
        config_module.save(self._cfg)
        self._apply_ghostty_theme_if_active()

    def _on_ghostty_decoration_changed(self, combo_row: Adw.ComboRow, _param) -> None:
        """Persist updated Ghostty window decoration selection."""
        decors = ("auto", "none", "client", "server")
        idx = combo_row.get_selected()
        self._cfg.ghostty_window_decoration = decors[idx] if idx < len(decors) else "auto"
        config_module.save(self._cfg)
        self._apply_ghostty_theme_if_active()

    def _apply_ghostty_theme_if_active(self) -> None:
        """Apply Ghostty theme and config stack immediately if integration is enabled."""
        if self._cfg.ghostty_integration:
            mode = theme_engine.get_current_mode()
            if mode in ("light", "dark"):
                ghostty.apply_theme(mode, self._cfg)

    def _on_detect_location(self, _button: Gtk.Button) -> None:
        """Request the current location from GeoClue2 via D-Bus.

        GeoClue2 must be installed and GNOME Location Services must be
        enabled in Settings → Privacy. If unavailable, an error toast is shown.
        """
        self._detect_button.set_sensitive(False)
        self._detect_button.set_label("Detecting…")

        try:
            self._start_geoclue_request()
        except Exception as exc:
            logger.warning("GeoClue2 location request failed: %s", exc)
            self._show_detect_error(str(exc))
            self._detect_button.set_sensitive(True)
            self._detect_button.set_label("Detect")

    def _start_geoclue_request(self) -> None:
        """Initiate a GeoClue2 D-Bus location request asynchronously."""
        # Add a 10-second timeout to prevent getting stuck
        self._geoclue_timeout_id = GLib.timeout_add_seconds(10, self._on_geoclue_timeout)

        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SYSTEM,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.GeoClue2",
            "/org/freedesktop/GeoClue2/Manager",
            "org.freedesktop.GeoClue2.Manager",
            None,
            self._on_geoclue_manager_ready,
        )

    def _on_geoclue_timeout(self) -> bool:
        """Fallback to IP-based location if GeoClue2 takes too long."""
        logger.warning("GeoClue2 request timed out — falling back to IP geolocation.")
        self._geoclue_timeout_id = None
        import threading
        threading.Thread(target=self._ip_fallback_request, daemon=True).start()
        return GLib.SOURCE_REMOVE

    def _ip_fallback_request(self) -> None:
        """Attempt IP-based geolocation using ipapi.co (runs in a background thread)."""
        import urllib.request
        import json
        try:
            req = urllib.request.Request(
                "https://ipapi.co/json/",
                headers={"User-Agent": "solaris/0.1.0 (https://github.com/notroot/solaris)"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if "latitude" not in data or "longitude" not in data:
                    raise ValueError("Invalid response from IP API")
                lat = float(data["latitude"])
                lon = float(data["longitude"])
                GLib.idle_add(self._apply_detected_location, lat, lon)
        except Exception as exc:
            GLib.idle_add(self._show_detect_error, f"IP fallback failed: {exc}")
            GLib.idle_add(self._reset_detect_button)

    def _on_geoclue_manager_ready(self, source, result) -> None:
        """Callback when GeoClue2 Manager proxy is ready."""
        try:
            manager = Gio.DBusProxy.new_for_bus_finish(result)
            manager.call(
                "GetClient",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self._on_geoclue_client_path,
            )
        except Exception as exc:
            GLib.idle_add(self._show_detect_error, f"GeoClue2 unavailable: {exc}")
            GLib.idle_add(self._reset_detect_button)

    def _on_geoclue_client_path(self, manager, result) -> None:
        """Callback when GeoClue2 returns a client object path."""
        try:
            (client_path,) = manager.call_finish(result).unpack()
            Gio.DBusProxy.new_for_bus(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.GeoClue2",
                client_path,
                "org.freedesktop.GeoClue2.Client",
                None,
                self._on_geoclue_client_ready,
            )
        except Exception as exc:
            GLib.idle_add(self._show_detect_error, f"GeoClue2 client error: {exc}")
            GLib.idle_add(self._reset_detect_button)

    def _on_geoclue_client_ready(self, source, result) -> None:
        """Set desktop ID and start GeoClue2 location updates."""
        try:
            client = Gio.DBusProxy.new_for_bus_finish(result)
            client.set_cached_property(
                "DesktopId", GLib.Variant("s", "solaris")
            )
            client.connect("g-signal", self._on_geoclue_signal)
            client.call(
                "Start",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                None,
            )
            self._geoclue_client = client  # keep reference
        except Exception as exc:
            GLib.idle_add(self._show_detect_error, f"GeoClue2 start error: {exc}")
            GLib.idle_add(self._reset_detect_button)

    def _on_geoclue_signal(self, proxy, sender, signal_name, params) -> None:
        """Handle GeoClue2 signals, specifically LocationUpdated."""
        if signal_name != "LocationUpdated":
            return

        _old_path, new_path = params.unpack()

        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SYSTEM,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.GeoClue2",
            new_path,
            "org.freedesktop.GeoClue2.Location",
            None,
            self._on_geoclue_location_ready,
        )

    def _on_geoclue_location_ready(self, source, result) -> None:
        """Extract lat/lon from the GeoClue2 Location object and update the UI."""
        try:
            location = Gio.DBusProxy.new_for_bus_finish(result)
            lat = location.get_cached_property("Latitude").get_double()
            lon = location.get_cached_property("Longitude").get_double()

            GLib.idle_add(self._apply_detected_location, lat, lon)
        except Exception as exc:
            GLib.idle_add(self._show_detect_error, f"Could not read location: {exc}")
        finally:
            GLib.idle_add(self._reset_detect_button)

    def _apply_detected_location(self, lat: float, lon: float) -> None:
        """Update the entry rows and save the detected coordinates."""
        self._lat_row.set_text(f"{lat:.6f}")
        self._lon_row.set_text(f"{lon:.6f}")
        self._cfg.latitude = lat
        self._cfg.longitude = lon
        config_module.save(self._cfg)
        self._refresh_solar_preview()

    def _reset_detect_button(self) -> None:
        """Re-enable the detect button after an async operation completes."""
        if self._geoclue_timeout_id is not None:
            GLib.source_remove(self._geoclue_timeout_id)
            self._geoclue_timeout_id = None

        self._detect_button.set_sensitive(True)
        self._detect_button.set_label("Detect")

    def _show_detect_error(self, message: str) -> None:
        """Show an error toast to the user."""
        toast = Adw.Toast(title=f"Location detection failed: {message}")
        toast.set_timeout(4)
        parent = self.get_root()
        if isinstance(parent, Adw.ApplicationWindow):
            overlay = parent.get_content()
            if isinstance(overlay, Adw.ToastOverlay):
                overlay.add_toast(toast)
