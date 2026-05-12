"""Solaris theme engine.

Applies GTK4, GNOME Shell, and color-scheme settings via gsettings.
Uses subprocess.run deliberately (not Gio.Settings) so that the
org.gnome.shell.extensions.user-theme schema is optional — it only
exists when the User Themes extension is installed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from solaris.config import SolarisConfig

logger = logging.getLogger(__name__)

THEME_SCAN_PATH = Path("/usr/share/themes")

# gsettings schema constants
_SCHEMA_INTERFACE = "org.gnome.desktop.interface"
_SCHEMA_USER_THEME = "org.gnome.shell.extensions.user-theme"

_KEY_GTK_THEME = "gtk-theme"
_KEY_COLOR_SCHEME = "color-scheme"
_KEY_SHELL_THEME_NAME = "name"


def _gsettings_set(schema: str, key: str, value: str) -> bool:
    """Run a single `gsettings set` command.

    Args:
        schema: The GSettings schema string.
        key:    The key within that schema.
        value:  The value to set (always passed as a string).

    Returns:
        True on success, False if the command failed (e.g. schema missing).
    """
    result = subprocess.run(
        ["gsettings", "set", schema, key, value],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "gsettings set %s %s failed (rc=%d): %s",
            schema, key, result.returncode, result.stderr.strip(),
        )
        return False
    return True


def _gsettings_get(schema: str, key: str) -> str | None:
    """Run a single `gsettings get` command.

    Args:
        schema: The GSettings schema string.
        key:    The key to read.

    Returns:
        The raw string value, or None on failure.
    """
    result = subprocess.run(
        ["gsettings", "get", schema, key],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "gsettings get %s %s failed (rc=%d): %s",
            schema, key, result.returncode, result.stderr.strip(),
        )
        return None
    return result.stdout.strip()


def _apply_gtk4_theme(theme_name: str) -> None:
    """Symlink GTK4 assets and CSS to ~/.config/gtk-4.0/ to theme Libadwaita apps.

    Modern GNOME / Libadwaita ignores the `gtk-theme` gsetting.
    """
    theme_dir = Path(f"/usr/share/themes/{theme_name}/gtk-4.0")
    if not theme_dir.is_dir():
        theme_dir = Path.home() / ".themes" / theme_name / "gtk-4.0"
        if not theme_dir.is_dir():
            logger.debug("No gtk-4.0 directory found for theme %s", theme_name)
            return

    gtk4_config_dir = Path.home() / ".config" / "gtk-4.0"
    gtk4_config_dir.mkdir(parents=True, exist_ok=True)

    # Clean existing links/files
    for item in ("assets", "gtk.css", "gtk-dark.css"):
        dest = gtk4_config_dir / item
        if dest.is_symlink() or dest.exists():
            if dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            else:
                dest.unlink()

    # Symlink new assets and CSS
    assets_src = theme_dir / "assets"
    if assets_src.exists():
        (gtk4_config_dir / "assets").symlink_to(assets_src)

    for css_file in ("gtk.css", "gtk-dark.css"):
        src = theme_dir / css_file
        if src.exists():
            (gtk4_config_dir / css_file).symlink_to(src)

    logger.debug("Symlinked GTK4 assets for %s", theme_name)


def apply_light(config: SolarisConfig) -> None:
    """Apply the light theme configuration from config.

    Sets GTK theme, color-scheme, and (optionally) the GNOME Shell theme.
    A missing User Themes extension is logged as a warning, not an error.

    Args:
        config: The current SolarisConfig to read theme names from.
    """
    logger.info("Applying light theme: gtk=%s", config.light_gtk_theme)

    _gsettings_set(_SCHEMA_INTERFACE, _KEY_GTK_THEME, config.light_gtk_theme)
    _gsettings_set(_SCHEMA_INTERFACE, _KEY_COLOR_SCHEME, config.light_color_scheme)
    _apply_gtk4_theme(config.light_gtk_theme)

    shell_ok = _gsettings_set(
        _SCHEMA_USER_THEME, _KEY_SHELL_THEME_NAME, config.light_shell_theme
    )
    if not shell_ok:
        logger.warning(
            "Shell theme not applied — is the 'User Themes' GNOME extension enabled?"
        )


def apply_dark(config: SolarisConfig) -> None:
    """Apply the dark theme configuration from config.

    Sets GTK theme, color-scheme, and (optionally) the GNOME Shell theme.
    A missing User Themes extension is logged as a warning, not an error.

    Args:
        config: The current SolarisConfig to read theme names from.
    """
    logger.info("Applying dark theme: gtk=%s", config.dark_gtk_theme)

    _gsettings_set(_SCHEMA_INTERFACE, _KEY_GTK_THEME, config.dark_gtk_theme)
    _gsettings_set(_SCHEMA_INTERFACE, _KEY_COLOR_SCHEME, config.dark_color_scheme)
    _apply_gtk4_theme(config.dark_gtk_theme)

    shell_ok = _gsettings_set(
        _SCHEMA_USER_THEME, _KEY_SHELL_THEME_NAME, config.dark_shell_theme
    )
    if not shell_ok:
        logger.warning(
            "Shell theme not applied — is the 'User Themes' GNOME extension enabled?"
        )


def get_current_mode() -> str:
    """Determine the active theme mode by reading color-scheme from gsettings.

    Returns:
        "light"   if color-scheme is 'prefer-light'
        "dark"    if color-scheme is 'prefer-dark'
        "unknown" if the value cannot be read or is unrecognised.
    """
    raw_value = _gsettings_get(_SCHEMA_INTERFACE, _KEY_COLOR_SCHEME)
    if raw_value is None:
        return "unknown"

    # gsettings returns GVariant strings with surrounding quotes: 'prefer-dark'
    clean_value = raw_value.strip("'\"")

    if clean_value in ("prefer-light", "default"):
        return "light"
    if clean_value == "prefer-dark":
        return "dark"

    logger.debug("Unrecognised color-scheme value: %r", raw_value)
    return "unknown"


def scan_themes(prefix: str = "Colloid") -> list[str]:
    """Scan /usr/share/themes for installed theme directories matching a prefix.

    Args:
        prefix: Only return themes whose names start with this string.
                Defaults to "Colloid". Pass "" to return all themes.

    Returns:
        A sorted list of matching theme directory names.
    """
    if not THEME_SCAN_PATH.is_dir():
        logger.warning("Theme directory %s does not exist.", THEME_SCAN_PATH)
        return []

    themes = [
        entry.name
        for entry in THEME_SCAN_PATH.iterdir()
        if entry.is_dir() and entry.name.startswith(prefix)
    ]
    themes.sort()
    logger.debug("Found %d themes with prefix %r.", len(themes), prefix)
    return themes
