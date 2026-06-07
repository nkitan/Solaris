"""Solaris Firefox userChrome.css integration.

Patches hex colour variables inside a clearly-delimited marker block
in the active Firefox profile's chrome/userChrome.css file.
"""

from __future__ import annotations

import configparser
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Marker delimiters that Solaris owns inside userChrome.css
MARKER_START = "/* SOLARIS_THEME_START */"
MARKER_END = "/* SOLARIS_THEME_END */"

# Colour pairs: (light_hex, dark_hex)
_BG_LIGHT = "#ffffff"
_BG_DARK = "#282828"
_TEXT_LIGHT = "#000000"
_TEXT_DARK = "#ebdbb2"

# Default CSS template appended when no marker block exists yet.
_DEFAULT_BLOCK = """\
/* SOLARIS_THEME_START */
:root {{
  --solaris-bg: {bg};
  --solaris-text: {text};
}}
/* SOLARIS_THEME_END */
"""

def _get_firefox_paths() -> tuple[Path, Path]:
    """Return the (firefox_dir, profiles_ini_path) to use."""
    # Check ~/.mozilla/firefox/profiles.ini
    dir_mozilla = Path.home() / ".mozilla" / "firefox"
    ini_mozilla = dir_mozilla / "profiles.ini"
    if ini_mozilla.exists():
        return dir_mozilla, ini_mozilla

    # Check ~/.config/mozilla/firefox/profiles.ini
    dir_config = Path.home() / ".config" / "mozilla" / "firefox"
    ini_config = dir_config / "profiles.ini"
    if ini_config.exists():
        return dir_config, ini_config

    # Default to ~/.mozilla/firefox/profiles.ini if neither exists
    return dir_mozilla, ini_mozilla


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def find_active_profile() -> Path | None:
    """Locate the active Firefox profile directory.

    Reads ~/.mozilla/firefox/profiles.ini or ~/.config/mozilla/firefox/profiles.ini
    and returns the path of the first profile marked Default=1, or the first profile
    in the [Profile0] section as a fallback.

    Returns:
        An absolute Path to the profile directory, or None if Firefox is not
        installed or no usable profile is found.
    """
    firefox_dir, profiles_ini = _get_firefox_paths()
    if not profiles_ini.exists():
        logger.warning(
            "Firefox profiles.ini not found at %s or %s.",
            Path.home() / ".mozilla" / "firefox" / "profiles.ini",
            Path.home() / ".config" / "mozilla" / "firefox" / "profiles.ini",
        )
        return None

    parser = configparser.ConfigParser()
    parser.read(profiles_ini, encoding="utf-8")

    default_profile_path: str | None = None
    fallback_profile_path: str | None = None

    for section in parser.sections():
        if not section.startswith("Profile"):
            continue

        is_relative = parser.getboolean(section, "IsRelative", fallback=True)
        raw_path = parser.get(section, "Path", fallback=None)
        is_default = parser.getboolean(section, "Default", fallback=False)

        if raw_path is None:
            continue

        resolved_path = (
            str(firefox_dir / raw_path) if is_relative else raw_path
        )

        if is_default:
            default_profile_path = resolved_path
        if fallback_profile_path is None:
            fallback_profile_path = resolved_path

    chosen = default_profile_path or fallback_profile_path
    if chosen is None:
        logger.warning("No usable Firefox profile found in %s.", profiles_ini)
        return None

    profile_path = Path(chosen)
    if not profile_path.is_dir():
        logger.warning("Firefox profile directory does not exist: %s", profile_path)
        return None

    logger.debug("Active Firefox profile: %s", profile_path)
    return profile_path


# ---------------------------------------------------------------------------
# chrome/ directory and userChrome.css handling
# ---------------------------------------------------------------------------

def ensure_chrome_dir(profile_path: Path) -> Path:
    """Return the chrome/ subdirectory, creating it if necessary.

    Args:
        profile_path: Absolute path to the Firefox profile root.

    Returns:
        Path to the chrome/ directory.
    """
    chrome_dir = (profile_path / "chrome").resolve()
    chrome_dir.mkdir(parents=True, exist_ok=True)
    return chrome_dir


def _read_user_chrome(chrome_dir: Path) -> str:
    """Return existing userChrome.css content, or an empty string."""
    user_chrome_path = chrome_dir / "userChrome.css"
    if user_chrome_path.exists():
        return user_chrome_path.read_text(encoding="utf-8")
    return ""


def _backup_user_chrome(chrome_dir: Path) -> None:
    """Create a .bak backup of userChrome.css if the file exists."""
    source = chrome_dir / "userChrome.css"
    if source.exists():
        destination = chrome_dir / "userChrome.css.bak"
        shutil.copy2(source, destination)
        logger.debug("Backup created: %s", destination)


def _build_replacement_block(mode: str) -> str:
    """Build the Solaris-owned CSS block for the given mode.

    Args:
        mode: "light" or "dark".

    Returns:
        The full CSS block string including marker comments.
    """
    if mode == "light":
        bg, text = _BG_LIGHT, _TEXT_LIGHT
    else:
        bg, text = _BG_DARK, _TEXT_DARK

    return _DEFAULT_BLOCK.format(bg=bg, text=text)


def _inject_block(existing_content: str, new_block: str) -> str:
    """Replace or append the Solaris block inside existing CSS content.

    If MARKER_START / MARKER_END delimiters are present, the content
    between them (inclusive) is replaced. Otherwise the block is appended.

    Args:
        existing_content: Current file content.
        new_block:        The replacement CSS block.

    Returns:
        Updated CSS content string.
    """
    start_idx = existing_content.find(MARKER_START)
    end_idx = existing_content.find(MARKER_END)

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        # Replace between markers (inclusive of both marker lines)
        end_of_block = end_idx + len(MARKER_END)
        updated = (
            existing_content[:start_idx]
            + new_block.rstrip("\n")
            + existing_content[end_of_block:]
        )
        return updated

    # No markers — append the block with a leading newline.
    logger.info("No Solaris marker block found — appending default block.")
    separator = "\n\n" if existing_content.rstrip() else ""
    return existing_content + separator + new_block


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_theme(mode: str) -> bool:
    """Patch userChrome.css in the active Firefox profile for the given mode.

    Finds the active profile, creates the chrome/ directory if needed,
    backs up the existing file, and injects/updates the Solaris colour block.

    Args:
        mode: "light" or "dark".

    Returns:
        True on success, False if Firefox is not set up or patching failed.
    """
    if mode not in ("light", "dark"):
        logger.error("apply_theme called with invalid mode %r. Expected 'light' or 'dark'.", mode)
        return False

    profile_path = find_active_profile()
    if profile_path is None:
        logger.warning("Skipping Firefox theme patch — no active profile found.")
        return False

    chrome_dir = ensure_chrome_dir(profile_path)
    existing_content = _read_user_chrome(chrome_dir)

    new_block = _build_replacement_block(mode)
    updated_content = _inject_block(existing_content, new_block)

    if existing_content == updated_content:
        logger.debug("Firefox userChrome.css is already up to date, skipping write.")
        return True

    _backup_user_chrome(chrome_dir)
    try:
        (chrome_dir / "userChrome.css").write_text(updated_content, encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write userChrome.css: %s", exc)
        return False

    logger.info("Firefox userChrome.css patched for mode=%r at %s", mode, chrome_dir)
    return True
