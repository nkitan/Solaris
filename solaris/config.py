"""Solaris configuration management.

Handles reading and writing the user's persistent settings to
~/.config/solaris/config.json via the XDG Base Directory specification.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from xdg import BaseDirectory

logger = logging.getLogger(__name__)

CONFIG_APP_NAME = "solaris"
CONFIG_FILE_NAME = "config.json"

# Default location: Pune, Maharashtra, India
DEFAULT_LATITUDE = 18.5
DEFAULT_LONGITUDE = 73.8


@dataclass
class SolarisConfig:
    """All persistent user settings for Solaris.

    Defaults are tuned for a Pune-based Colloid-theme user,
    but every field is independently configurable.
    """

    # --- Location ---
    latitude: float = DEFAULT_LATITUDE
    longitude: float = DEFAULT_LONGITUDE

    # --- GTK Themes ---
    light_gtk_theme: str = "Colloid-Light"
    dark_gtk_theme: str = "Colloid-Dark"

    # --- GNOME Shell Themes (User Themes extension) ---
    light_shell_theme: str = "Colloid-Light"
    dark_shell_theme: str = "Colloid-Dark"

    # --- Color Scheme (prefer-light / prefer-dark) ---
    light_color_scheme: str = "prefer-light"
    dark_color_scheme: str = "prefer-dark"

    # --- Firefox Integration ---
    firefox_integration: bool = True

    # --- Override Mode ---
    # None  = follow solar schedule automatically
    # "light" / "dark" = manual override
    override_mode: str | None = None

    def __post_init__(self) -> None:
        """Validate coordinate ranges immediately after construction."""
        _validate_latitude(self.latitude)
        _validate_longitude(self.longitude)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_latitude(value: float) -> None:
    """Raise ValueError if latitude is out of the valid WGS-84 range."""
    if not -90.0 <= value <= 90.0:
        raise ValueError(f"Latitude must be between -90 and 90, got {value!r}")


def _validate_longitude(value: float) -> None:
    """Raise ValueError if longitude is out of the valid WGS-84 range."""
    if not -180.0 <= value <= 180.0:
        raise ValueError(f"Longitude must be between -180 and 180, got {value!r}")


def _config_dir() -> Path:
    """Return the XDG config directory for Solaris, creating it if needed."""
    return Path(BaseDirectory.save_config_path(CONFIG_APP_NAME))


def _config_path() -> Path:
    """Return the full path to the config JSON file."""
    return _config_dir() / CONFIG_FILE_NAME


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load() -> SolarisConfig:
    """Load config from disk, returning defaults if the file is absent or corrupt.

    Returns:
        A populated SolarisConfig dataclass.
    """
    config_path = _config_path()

    if not config_path.exists():
        logger.info("No config file found at %s — using defaults.", config_path)
        return SolarisConfig()

    try:
        raw_text = config_path.read_text(encoding="utf-8")
        raw_data: dict = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read config (%s) — using defaults: %s", config_path, exc)
        return SolarisConfig()

    # Merge known keys from disk, ignore unknown keys so we remain
    # forward-compatible with older config versions.
    known_fields = {f.name for f in SolarisConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered_data = {k: v for k, v in raw_data.items() if k in known_fields}

    try:
        return SolarisConfig(**filtered_data)
    except (TypeError, ValueError) as exc:
        logger.warning("Config data is invalid (%s) — using defaults: %s", config_path, exc)
        return SolarisConfig()


def save(config: SolarisConfig) -> None:
    """Persist a SolarisConfig to disk atomically.

    Uses a write-to-temp-then-rename strategy to prevent corruption
    if the process is interrupted mid-write.

    Args:
        config: The configuration to persist.
    """
    config_dir = _config_dir()
    config_path = _config_path()

    raw_data = asdict(config)
    serialized = json.dumps(raw_data, indent=2, ensure_ascii=False)

    try:
        # Write to a temp file in the same directory so rename() is atomic.
        fd, tmp_path_str = tempfile.mkstemp(dir=config_dir, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(serialized)
            os.replace(tmp_path_str, config_path)
        except Exception:
            # Clean up temp file if rename failed.
            Path(tmp_path_str).unlink(missing_ok=True)
            raise
    except OSError as exc:
        logger.error("Failed to save config to %s: %s", config_path, exc)
        raise
    else:
        logger.info("Config saved to %s.", config_path)
