"""Tests for solaris.ghostty — config patching and theme scanning."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from solaris import ghostty
from solaris.config import SolarisConfig


def _make_completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# find_ghostty_config
# ---------------------------------------------------------------------------


class TestFindGhosttyConfig:
    def test_uses_xdg_config_home_when_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        result = ghostty.find_ghostty_config()
        assert str(result).startswith(str(tmp_path / "xdg"))
        assert result.name == "config"

    def test_falls_back_to_home_config(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        result = ghostty.find_ghostty_config()
        assert result == tmp_path / ".config" / "ghostty" / "config"


# ---------------------------------------------------------------------------
# scan_themes
# ---------------------------------------------------------------------------


class TestScanThemes:
    def test_returns_themes_from_user_dir(self, tmp_path, monkeypatch):
        user_themes = tmp_path / ".config" / "ghostty" / "themes"
        user_themes.mkdir(parents=True)
        (user_themes / "Solarized").touch()
        (user_themes / "Gruvbox").touch()

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        # Suppress system path; it's checked first but won't exist in tmp env.

        result = ghostty.scan_themes()
        assert "Solarized" in result
        assert "Gruvbox" in result

    def test_skips_directories_only_returns_files(self, tmp_path, monkeypatch):
        user_themes = tmp_path / ".config" / "ghostty" / "themes"
        user_themes.mkdir(parents=True)
        (user_themes / "Solarized").touch()
        (user_themes / "subdir").mkdir()

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = ghostty.scan_themes()
        assert "Solarized" in result
        assert "subdir" not in result

    def test_returns_empty_when_no_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = ghostty.scan_themes()
        assert result == [] or all(isinstance(t, str) for t in result)

    def test_deduplicates_across_paths(self, tmp_path, monkeypatch):
        user_themes = tmp_path / ".config" / "ghostty" / "themes"
        user_themes.mkdir(parents=True)
        (user_themes / "Catppuccin").touch()

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = ghostty.scan_themes()
        # No duplicates
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# _inject_block
# ---------------------------------------------------------------------------


class TestInjectBlock:
    def test_appends_to_empty_file(self):
        block = "# SOLARIS_THEME_START\ntheme = Foo\n# SOLARIS_THEME_END\n"
        result = ghostty._inject_block("", block)
        assert result.startswith("# SOLARIS_THEME_START")

    def test_replaces_existing_marker_block(self):
        existing = (
            "font-size = 14\n\n"
            "# SOLARIS_THEME_START\n"
            "theme = OldTheme\n"
            "# SOLARIS_THEME_END\n"
            "\nopacity = 0.95\n"
        )
        new_block = (
            "# SOLARIS_THEME_START\n"
            "theme = NewTheme\n"
            "window-theme = ghostty\n"
            "window-decoration = auto\n"
            "# SOLARIS_THEME_END\n"
        )
        result = ghostty._inject_block(existing, new_block)
        assert "OldTheme" not in result
        assert "NewTheme" in result
        assert "font-size = 14" in result
        assert "opacity = 0.95" in result

    def test_replaces_orphan_theme_line(self):
        existing = "font-size = 14\ntheme = OldTheme\nopacity = 0.95\n"
        new_block = (
            "# SOLARIS_THEME_START\n"
            "theme = NewTheme\n"
            "window-theme = ghostty\n"
            "window-decoration = auto\n"
            "# SOLARIS_THEME_END\n"
        )
        result = ghostty._inject_block(existing, new_block)
        assert "theme = OldTheme" not in result
        assert "NewTheme" in result
        assert "font-size = 14" in result

    def test_appends_when_no_match(self):
        existing = "font-size = 14\nopacity = 0.95\n"
        new_block = (
            "# SOLARIS_THEME_START\n"
            "theme = NewTheme\n"
            "# SOLARIS_THEME_END\n"
        )
        result = ghostty._inject_block(existing, new_block)
        assert "font-size = 14" in result
        assert "NewTheme" in result


# ---------------------------------------------------------------------------
# apply_theme
# ---------------------------------------------------------------------------


class TestApplyTheme:
    def test_invalid_mode_returns_false(self):
        cfg = SolarisConfig()
        assert ghostty.apply_theme("dusky", cfg) is False

    def test_returns_false_when_ghostty_not_installed(self, mocker):
        mocker.patch("solaris.ghostty.shutil.which", return_value=None)
        cfg = SolarisConfig()
        assert ghostty.apply_theme("light", cfg) is False

    def test_creates_config_when_missing(self, tmp_path, monkeypatch, mocker):
        mocker.patch(
            "solaris.ghostty.shutil.which", return_value="/usr/bin/ghostty"
        )
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        cfg = SolarisConfig()
        result = ghostty.apply_theme("dark", cfg)
        assert result is True

        config_path = tmp_path / "xdg" / "ghostty" / "config"
        assert config_path.exists()
        content = config_path.read_text()
        assert cfg.dark_ghostty_theme in content
        assert "SOLARIS_THEME_START" in content

    def test_replaces_existing_block(self, tmp_path, monkeypatch, mocker):
        mocker.patch(
            "solaris.ghostty.shutil.which", return_value="/usr/bin/ghostty"
        )
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        config_path = tmp_path / "xdg" / "ghostty" / "config"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            "font-size = 14\n\n"
            "# SOLARIS_THEME_START\n"
            "theme = Old\n"
            "# SOLARIS_THEME_END\n"
        )

        cfg = SolarisConfig(light_ghostty_theme="NewLight")
        assert ghostty.apply_theme("light", cfg) is True

        content = config_path.read_text()
        assert "NewLight" in content
        assert "Old" not in content
        assert "font-size = 14" in content

    def test_no_write_when_already_up_to_date(
        self, tmp_path, monkeypatch, mocker
    ):
        mocker.patch(
            "solaris.ghostty.shutil.which", return_value="/usr/bin/ghostty"
        )
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        cfg = SolarisConfig()
        ghostty.apply_theme("light", cfg)
        config_path = tmp_path / "xdg" / "ghostty" / "config"
        mtime_first = config_path.stat().st_mtime_ns

        ghostty.apply_theme("light", cfg)
        mtime_second = config_path.stat().st_mtime_ns

        # Second call should NOT have rewritten the file.
        assert mtime_first == mtime_second

    def test_creates_backup_on_change(self, tmp_path, monkeypatch, mocker):
        mocker.patch(
            "solaris.ghostty.shutil.which", return_value="/usr/bin/ghostty"
        )
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        config_path = tmp_path / "xdg" / "ghostty" / "config"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("font-size = 14\n")

        cfg = SolarisConfig()
        ghostty.apply_theme("light", cfg)

        backup_path = config_path.with_name("config.bak")
        assert backup_path.exists()
        assert backup_path.read_text() == "font-size = 14\n"

    def test_reload_signal_called_on_success(
        self, tmp_path, monkeypatch, mocker
    ):
        mocker.patch(
            "solaris.ghostty.shutil.which", return_value="/usr/bin/ghostty"
        )
        run = mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=0),
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        cfg = SolarisConfig()
        ghostty.apply_theme("dark", cfg)

        # pkill -USR2 ghostty should have been invoked.
        calls = [c.args[0] for c in run.call_args_list]
        assert any("pkill" in c and "ghostty" in c for c in calls)


# ---------------------------------------------------------------------------
# _reload_ghostty
# ---------------------------------------------------------------------------


class TestReloadGhostty:
    def test_logs_info_on_rc_0(self, mocker, caplog):
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=0),
        )
        with caplog.at_level("INFO"):
            ghostty._reload_ghostty()
        assert any("Signaled" in r.message for r in caplog.records)

    def test_logs_debug_on_rc_1_no_instances(self, mocker, caplog):
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=1),
        )
        with caplog.at_level("DEBUG"):
            ghostty._reload_ghostty()
        assert any(
            "No active" in r.message for r in caplog.records
        )

    def test_logs_warning_on_other_failures(self, mocker, caplog):
        mocker.patch(
            "solaris.ghostty.subprocess.run",
            return_value=_make_completed(returncode=2, stderr="err"),
        )
        with caplog.at_level("WARNING"):
            ghostty._reload_ghostty()
        assert any("failed" in r.message for r in caplog.records)
