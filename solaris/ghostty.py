"""Solaris Ghostty configuration integration.

Patches theme settings inside a clearly-delimited marker block
in the Ghostty configuration file (~/.config/ghostty/config)
and reloads running instances via SIGUSR2.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from solaris.config import SolarisConfig

logger = logging.getLogger(__name__)

MARKER_START = "# SOLARIS_THEME_START"
MARKER_END = "# SOLARIS_THEME_END"

_DEFAULT_BLOCK = """\
# SOLARIS_THEME_START
theme = {theme}
window-theme = ghostty
window-decoration = {window_decoration}
# SOLARIS_THEME_END
"""


def find_ghostty_config() -> Path:
    """Locate the Ghostty config file path.

    Returns:
        Path to the configuration file.
    """
    config_dir = os.environ.get("XDG_CONFIG_HOME")
    if config_dir:
        return Path(config_dir) / "ghostty" / "config"
    return Path.home() / ".config" / "ghostty" / "config"


def scan_themes() -> list[str]:
    """Scan for Ghostty themes in system and user directories.

    Returns:
        A sorted list of unique theme names.
    """
    paths = [
        Path("/usr/share/ghostty/themes"),
        Path.home() / ".config" / "ghostty" / "themes",
    ]
    themes = set()
    for p in paths:
        if p.is_dir():
            try:
                for entry in p.iterdir():
                    if entry.is_file():
                        themes.add(entry.name)
            except OSError as exc:
                logger.debug("Failed to list themes in %s: %s", p, exc)

    sorted_themes = sorted(list(themes))
    logger.debug("Found %d Ghostty themes.", len(sorted_themes))
    return sorted_themes


def apply_theme(mode: str, cfg: SolarisConfig) -> bool:
    """Patch Ghostty config for the given mode and reload running instances.

    Args:
        mode: "light" or "dark".
        cfg:  The loaded SolarisConfig.

    Returns:
        True on success, False if patching failed.
    """
    if mode not in ("light", "dark"):
        logger.error(
            "apply_theme called with invalid mode %r. Expected 'light' or 'dark'.",
            mode,
        )
        return False

    # Check if ghostty is installed
    if not shutil.which("ghostty"):
        logger.debug("Ghostty executable not found on path, skipping.")
        return False

    config_path = find_ghostty_config()

    # If the directory doesn't exist, create it
    config_path.parent.mkdir(parents=True, exist_ok=True)

    active_theme = cfg.light_ghostty_theme if mode == "light" else cfg.dark_ghostty_theme

    new_block = _DEFAULT_BLOCK.format(
        theme=active_theme,
        window_decoration=cfg.ghostty_window_decoration,
    )

    existing_content = ""
    if config_path.exists():
        try:
            existing_content = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to read Ghostty config: %s", exc)
            return False

    updated_content = _inject_block(existing_content, new_block)

    if existing_content == updated_content:
        logger.debug("Ghostty config is already up to date, skipping write.")
        return True

    # Create a backup
    try:
        backup_path = config_path.with_name("config.bak")
        shutil.copy2(config_path, backup_path)
        logger.debug("Backup created: %s", backup_path)
    except OSError as exc:
        logger.warning("Failed to create Ghostty config backup: %s", exc)

    try:
        config_path.write_text(updated_content, encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write Ghostty config: %s", exc)
        return False

    logger.info(
        "Ghostty config patched for mode=%r with theme=%r",
        mode,
        active_theme,
    )

    # Reload running ghostty instances without closing them
    _reload_ghostty()
    return True


def _inject_block(existing_content: str, new_block: str) -> str:
    """Replace or append the Solaris block inside existing Ghostty config content.

    If markers are present, replaces everything between them. Otherwise, looks
    for an existing active (uncommented) `theme =` line and replaces it to avoid
    duplicates. If neither is found, appends the block to the end of the file.
    """
    start_idx = existing_content.find(MARKER_START)
    end_idx = existing_content.find(MARKER_END)

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        end_of_block = end_idx + len(MARKER_END)
        updated = (
            existing_content[:start_idx]
            + new_block.rstrip("\n")
            + existing_content[end_of_block:]
        )
        return updated

    import re

    pattern = re.compile(r"^[ \t]*theme[ \t]*=.*$", re.MULTILINE)
    match = pattern.search(existing_content)
    if match:
        logger.info(
            "Found existing theme setting, replacing it with Solaris block."
        )
        start, end = match.span()
        updated = (
            existing_content[:start]
            + new_block.rstrip("\n")
            + existing_content[end:]
        )
        return updated

    logger.info(
        "No Solaris marker block or theme setting found — appending default block."
    )
    separator = "\n\n" if existing_content.rstrip() else ""
    return existing_content + separator + new_block


def _reload_ghostty() -> None:
    """Reload all running Ghostty instances by sending SIGUSR2."""
    result = subprocess.run(
        ["pkill", "-USR2", "ghostty"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        logger.info("Signaled running Ghostty instances to reload config.")
    elif result.returncode == 1:
        logger.debug("No active Ghostty instances found to reload.")
    else:
        logger.warning(
            "pkill -USR2 ghostty failed with rc=%d: %s",
            result.returncode,
            result.stderr.strip(),
        )
