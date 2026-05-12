"""Solaris Adw.Application — GUI entry point.

Constructs the main application window with an Adw.ViewSwitcher
that toggles between the Status dashboard and the Preferences page.
"""

from __future__ import annotations

import logging
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from solaris import __app_id__, __version__
from solaris import config as config_module
from solaris.ui.preferences_page import PreferencesPage
from solaris.ui.status_page import StatusPage

logger = logging.getLogger(__name__)


class SolarisWindow(Adw.ApplicationWindow):
    """The single main window for the Solaris GUI."""

    def __init__(self, application: Adw.Application, cfg: config_module.SolarisConfig) -> None:
        super().__init__(application=application)

        self._cfg = cfg
        self._status_page: StatusPage | None = None

        self.set_title("Solaris")
        self.set_default_size(480, 640)
        self.set_resizable(True)

        self._build_ui()

    def _build_ui(self) -> None:
        """Assemble the full window layout."""
        # Root: ToastOverlay → NavigationView (header + content)
        toast_overlay = Adw.ToastOverlay()

        # ViewStack holds the two pages.
        stack = Adw.ViewStack()

        self._status_page = StatusPage(cfg=self._cfg)
        stack.add_titled_with_icon(
            self._status_page,
            "status",
            "Status",
            "dialog-information-symbolic",
        )

        prefs_page = PreferencesPage(cfg=self._cfg)
        stack.add_titled_with_icon(
            prefs_page,
            "preferences",
            "Preferences",
            "emblem-system-symbolic",
        )

        # ViewSwitcher bar at the bottom (mobile-friendly).
        switcher_bar = Adw.ViewSwitcherBar()
        switcher_bar.set_stack(stack)
        switcher_bar.set_reveal(True)

        # Header bar with top ViewSwitcher (wide screens).
        header_bar = Adw.HeaderBar()
        header_bar.set_centering_policy(Adw.CenteringPolicy.STRICT)

        top_switcher = Adw.ViewSwitcher()
        top_switcher.set_stack(stack)
        top_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header_bar.set_title_widget(top_switcher)

        # Version label in the header.
        version_label = Gtk.Label(label=f"v{__version__}")
        version_label.add_css_class("dim-label")
        version_label.add_css_class("caption")
        header_bar.pack_end(version_label)

        # Assemble: ToolbarView stacks header + scrollable content + switcher bar.
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header_bar)
        toolbar_view.set_content(stack)
        toolbar_view.add_bottom_bar(switcher_bar)

        toast_overlay.set_child(toolbar_view)
        self.set_content(toast_overlay)

    def do_close_request(self) -> bool:
        """Clean up GLib timers before the window is destroyed."""
        if self._status_page is not None:
            self._status_page.cleanup()
        return False  # allow the window to close


class SolarisApplication(Adw.Application):
    """The Adw.Application subclass for Solaris."""

    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._window: SolarisWindow | None = None

    def do_activate(self) -> None:
        """Present the main window, creating it if necessary."""
        cfg = config_module.load()

        if self._window is None:
            self._window = SolarisWindow(application=self, cfg=cfg)

        self._window.present()

    def do_startup(self) -> None:
        """Set up application-level actions."""
        Adw.Application.do_startup(self)
        self._setup_actions()

    def _setup_actions(self) -> None:
        """Register Gio actions for keyboard shortcuts."""
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Primary>q"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """GUI entry point called by the `solaris-gui` console script."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    app = SolarisApplication()
    exit_code = app.run(sys.argv)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
