"""Tests for solaris.config — round-trip, defaults, validation, error handling."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from solaris import config as config_module
from solaris.config import (
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    SCHEDULE_MODE_MANUAL,
    SCHEDULE_MODE_SOLAR,
    SCHEDULE_MODE_TIME,
    SCHEDULE_MODES,
    SolarisConfig,
    _validate_ghostty_window_decoration,
    _validate_hhmm,
    _validate_latitude,
    _validate_longitude,
    _validate_schedule_mode,
    load,
    save,
)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestSolarisConfigDefaults:
    """Verify the dataclass exposes the documented default values."""

    def test_default_location_is_pune(self):
        cfg = SolarisConfig()
        assert cfg.latitude == DEFAULT_LATITUDE
        assert cfg.longitude == DEFAULT_LONGITUDE

    def test_default_gtk_themes(self):
        cfg = SolarisConfig()
        assert cfg.light_gtk_theme == "Colloid-Light"
        assert cfg.dark_gtk_theme == "Colloid-Dark"

    def test_default_shell_themes(self):
        cfg = SolarisConfig()
        assert cfg.light_shell_theme == "Colloid-Light"
        assert cfg.dark_shell_theme == "Colloid-Dark"

    def test_default_color_schemes(self):
        cfg = SolarisConfig()
        assert cfg.light_color_scheme == "prefer-light"
        assert cfg.dark_color_scheme == "prefer-dark"

    def test_default_integrations_enabled(self):
        cfg = SolarisConfig()
        assert cfg.firefox_integration is True
        assert cfg.ghostty_integration is True

    def test_default_schedule_is_solar(self):
        cfg = SolarisConfig()
        assert cfg.schedule_mode == SCHEDULE_MODE_SOLAR

    def test_default_manual_mode_is_dark(self):
        cfg = SolarisConfig()
        assert cfg.manual_mode == "dark"

    def test_default_time_windows(self):
        cfg = SolarisConfig()
        assert cfg.time_light_start == "07:00"
        assert cfg.time_dark_start == "20:00"

    def test_follow_dark_style_default_off(self):
        cfg = SolarisConfig()
        assert cfg.follow_dark_style is False

    def test_default_ghostty_themes(self):
        cfg = SolarisConfig()
        assert cfg.light_ghostty_theme == "Catppuccin Latte"
        assert cfg.dark_ghostty_theme == "Catppuccin Frappe"
        assert cfg.ghostty_window_decoration == "auto"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """All validators raise on out-of-range input and pass on valid input."""

    @pytest.mark.parametrize("lat", [-90.0, -45.0, 0.0, 18.5, 90.0])
    def test_valid_latitudes(self, lat):
        _validate_latitude(lat)  # should not raise

    @pytest.mark.parametrize("lat", [-90.1, 90.1, 1000.0, -1000.0])
    def test_invalid_latitudes(self, lat):
        with pytest.raises(ValueError, match="Latitude"):
            _validate_latitude(lat)

    @pytest.mark.parametrize("lon", [-180.0, -100.0, 0.0, 73.8, 180.0])
    def test_valid_longitudes(self, lon):
        _validate_longitude(lon)

    @pytest.mark.parametrize("lon", [-180.1, 180.1, 360.0, -360.0])
    def test_invalid_longitudes(self, lon):
        with pytest.raises(ValueError, match="Longitude"):
            _validate_longitude(lon)

    @pytest.mark.parametrize("mode", list(SCHEDULE_MODES))
    def test_valid_schedule_modes(self, mode):
        _validate_schedule_mode(mode)

    @pytest.mark.parametrize("mode", ["", "auto", "SOLAR", "Manual"])
    def test_invalid_schedule_modes(self, mode):
        with pytest.raises(ValueError, match="schedule_mode"):
            _validate_schedule_mode(mode)

    @pytest.mark.parametrize(
        "hhmm",
        ["00:00", "07:00", "09:30", "12:45", "23:59"],
    )
    def test_valid_hhmm(self, hhmm):
        _validate_hhmm(hhmm)

    @pytest.mark.parametrize(
        "hhmm",
        ["24:00", "7:00", "07:60", "abc", "12-30", "", "12:5"],
    )
    def test_invalid_hhmm(self, hhmm):
        with pytest.raises(ValueError):
            _validate_hhmm(hhmm)

    def test_invalid_hhmm_field_name_in_error(self):
        with pytest.raises(ValueError, match="time_dark_start"):
            _validate_hhmm("nope", field_name="time_dark_start")

    @pytest.mark.parametrize("v", ["auto", "none", "client", "server"])
    def test_valid_ghostty_decoration(self, v):
        _validate_ghostty_window_decoration(v)

    @pytest.mark.parametrize("v", ["", "AUTO", "default", "csd"])
    def test_invalid_ghostty_decoration(self, v):
        with pytest.raises(ValueError, match="ghostty_window_decoration"):
            _validate_ghostty_window_decoration(v)


class TestPostInitValidation:
    """SolarisConfig() raises eagerly if any field fails validation."""

    def test_bad_latitude_raises(self):
        with pytest.raises(ValueError):
            SolarisConfig(latitude=91.0)

    def test_bad_longitude_raises(self):
        with pytest.raises(ValueError):
            SolarisConfig(longitude=-200.0)

    def test_bad_schedule_mode_raises(self):
        with pytest.raises(ValueError):
            SolarisConfig(schedule_mode="auto")

    def test_bad_time_light_start_raises(self):
        with pytest.raises(ValueError):
            SolarisConfig(time_light_start="25:00")

    def test_bad_time_dark_start_raises(self):
        with pytest.raises(ValueError):
            SolarisConfig(time_dark_start="abc")

    def test_bad_ghostty_decoration_raises(self):
        with pytest.raises(ValueError):
            SolarisConfig(ghostty_window_decoration="csd")


# ---------------------------------------------------------------------------
# load() / save() round-trip
# ---------------------------------------------------------------------------


class TestLoadSaveRoundTrip:
    """Verify save() then load() produces identical configuration."""

    def test_default_load_when_no_file(self, tmp_xdg_config_home):
        cfg = load()
        assert cfg == SolarisConfig()

    def test_save_then_load_preserves_all_fields(self, tmp_xdg_config_home):
        original = SolarisConfig(
            latitude=51.5074,
            longitude=-0.1278,
            light_gtk_theme="Adwaita",
            dark_gtk_theme="Adwaita-dark",
            firefox_integration=False,
            ghostty_integration=False,
            schedule_mode=SCHEDULE_MODE_TIME,
            time_light_start="06:30",
            time_dark_start="19:15",
            follow_dark_style=True,
            ghostty_window_decoration="none",
        )
        save(original)
        loaded = load()
        assert loaded == original

    def test_save_creates_file(self, tmp_xdg_config_home):
        cfg = SolarisConfig()
        save(cfg)
        path = tmp_xdg_config_home / "solaris" / "config.json"
        assert path.exists()

    def test_saved_file_is_valid_json(self, tmp_xdg_config_home):
        cfg = SolarisConfig(latitude=10.0, longitude=20.0)
        save(cfg)
        path = tmp_xdg_config_home / "solaris" / "config.json"
        data = json.loads(path.read_text())
        assert data["latitude"] == 10.0
        assert data["longitude"] == 20.0

    def test_saved_file_contains_all_fields(self, tmp_xdg_config_home):
        cfg = SolarisConfig()
        save(cfg)
        path = tmp_xdg_config_home / "solaris" / "config.json"
        data = json.loads(path.read_text())
        for field in fields(SolarisConfig):
            assert field.name in data


# ---------------------------------------------------------------------------
# load() error tolerance
# ---------------------------------------------------------------------------


class TestLoadErrorTolerance:
    """load() falls back to defaults rather than crashing on bad input."""

    def test_corrupt_json_returns_defaults(self, tmp_xdg_config_home):
        path = tmp_xdg_config_home / "solaris"
        path.mkdir(parents=True, exist_ok=True)
        (path / "config.json").write_text("{this is not json")

        cfg = load()
        assert cfg == SolarisConfig()

    def test_unknown_keys_are_ignored(self, tmp_xdg_config_home):
        path = tmp_xdg_config_home / "solaris"
        path.mkdir(parents=True, exist_ok=True)
        data = {"latitude": 5.0, "some_future_field": "value"}
        (path / "config.json").write_text(json.dumps(data))

        cfg = load()
        assert cfg.latitude == 5.0
        # Other fields use defaults.
        assert cfg.longitude == DEFAULT_LONGITUDE

    def test_invalid_field_value_returns_defaults(self, tmp_xdg_config_home):
        path = tmp_xdg_config_home / "solaris"
        path.mkdir(parents=True, exist_ok=True)
        data = {"latitude": 999.0}  # out of range
        (path / "config.json").write_text(json.dumps(data))

        cfg = load()
        assert cfg == SolarisConfig()

    def test_empty_file_returns_defaults(self, tmp_xdg_config_home):
        path = tmp_xdg_config_home / "solaris"
        path.mkdir(parents=True, exist_ok=True)
        (path / "config.json").write_text("")

        cfg = load()
        assert cfg == SolarisConfig()


# ---------------------------------------------------------------------------
# Atomic save
# ---------------------------------------------------------------------------


class TestAtomicSave:
    """The save() implementation should clean up its temp file on failure."""

    def test_save_overwrites_existing_file(self, tmp_xdg_config_home):
        save(SolarisConfig(latitude=10.0))
        save(SolarisConfig(latitude=20.0))

        cfg = load()
        assert cfg.latitude == 20.0

    def test_no_temp_files_left_behind(self, tmp_xdg_config_home):
        save(SolarisConfig())
        config_dir = tmp_xdg_config_home / "solaris"
        leftovers = list(config_dir.glob("*.tmp"))
        assert leftovers == []

    def test_save_raises_on_oserror(
        self, tmp_xdg_config_home, monkeypatch
    ):
        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("tempfile.mkstemp", boom)

        with pytest.raises(OSError, match="disk full"):
            save(SolarisConfig())
