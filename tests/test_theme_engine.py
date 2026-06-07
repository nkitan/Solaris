"""Tests for solaris.theme_engine — mocked subprocess for gsettings calls."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from solaris import theme_engine
from solaris.config import SolarisConfig


def _make_completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Build a stub subprocess.CompletedProcess."""
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# _gsettings_get / _gsettings_set
# ---------------------------------------------------------------------------


class TestGsettingsGet:
    def test_returns_stripped_value_on_success(self, mocker):
        mocker.patch(
            "solaris.theme_engine.subprocess.run",
            return_value=_make_completed(stdout="'prefer-dark'\n"),
        )
        assert theme_engine._gsettings_get("schema", "key") == "'prefer-dark'"

    def test_returns_none_on_failure(self, mocker):
        mocker.patch(
            "solaris.theme_engine.subprocess.run",
            return_value=_make_completed(returncode=1, stderr="no such schema"),
        )
        assert theme_engine._gsettings_get("schema", "key") is None


class TestGsettingsSet:
    def test_skips_when_value_already_correct(self, mocker):
        run = mocker.patch(
            "solaris.theme_engine.subprocess.run",
            return_value=_make_completed(stdout="'prefer-dark'"),
        )
        result = theme_engine._gsettings_set(
            "org.gnome.desktop.interface", "color-scheme", "prefer-dark"
        )
        assert result is True
        # Only the `get` call should have been made — no `set`.
        assert run.call_count == 1
        assert run.call_args.args[0][1] == "get"

    def test_sets_when_value_differs(self, mocker):
        # First call: get returns 'prefer-light'; second: set succeeds.
        run = mocker.patch(
            "solaris.theme_engine.subprocess.run",
            side_effect=[
                _make_completed(stdout="'prefer-light'"),
                _make_completed(returncode=0),
            ],
        )
        assert theme_engine._gsettings_set(
            "org.gnome.desktop.interface", "color-scheme", "prefer-dark"
        ) is True
        assert run.call_count == 2
        # Verify the set command shape.
        set_args = run.call_args_list[1].args[0]
        assert set_args == [
            "gsettings", "set",
            "org.gnome.desktop.interface", "color-scheme", "prefer-dark",
        ]

    def test_returns_false_when_set_fails(self, mocker):
        mocker.patch(
            "solaris.theme_engine.subprocess.run",
            side_effect=[
                _make_completed(stdout="'old'"),
                _make_completed(returncode=1, stderr="schema missing"),
            ],
        )
        assert theme_engine._gsettings_set("schema", "key", "value") is False

    def test_sets_when_get_fails(self, mocker):
        # If we can't read the current value, we should attempt the set anyway.
        mocker.patch(
            "solaris.theme_engine.subprocess.run",
            side_effect=[
                _make_completed(returncode=1),  # get fails
                _make_completed(returncode=0),  # set ok
            ],
        )
        assert theme_engine._gsettings_set("schema", "key", "value") is True


# ---------------------------------------------------------------------------
# apply_light / apply_dark
# ---------------------------------------------------------------------------


class TestApplyLight:
    def test_calls_gsettings_for_each_key(self, mocker):
        mock_set = mocker.patch(
            "solaris.theme_engine._gsettings_set", return_value=True
        )
        mocker.patch("solaris.theme_engine._apply_gtk4_theme")

        cfg = SolarisConfig()
        theme_engine.apply_light(cfg)

        keys = [c.args for c in mock_set.call_args_list]
        assert (
            "org.gnome.desktop.interface", "gtk-theme", cfg.light_gtk_theme,
        ) in keys
        assert (
            "org.gnome.desktop.interface", "color-scheme",
            cfg.light_color_scheme,
        ) in keys
        assert (
            "org.gnome.shell.extensions.user-theme", "name",
            cfg.light_shell_theme,
        ) in keys

    def test_warns_when_shell_theme_set_fails(self, mocker, caplog):
        # gtk + color-scheme succeed; shell theme set fails (no extension).
        mocker.patch(
            "solaris.theme_engine._gsettings_set",
            side_effect=[True, True, False],
        )
        mocker.patch("solaris.theme_engine._apply_gtk4_theme")

        with caplog.at_level("WARNING"):
            theme_engine.apply_light(SolarisConfig())
        assert any("User Themes" in r.message for r in caplog.records)


class TestApplyDark:
    def test_calls_gsettings_for_each_key(self, mocker):
        mock_set = mocker.patch(
            "solaris.theme_engine._gsettings_set", return_value=True
        )
        mocker.patch("solaris.theme_engine._apply_gtk4_theme")

        cfg = SolarisConfig()
        theme_engine.apply_dark(cfg)

        keys = [c.args for c in mock_set.call_args_list]
        assert (
            "org.gnome.desktop.interface", "gtk-theme", cfg.dark_gtk_theme,
        ) in keys
        assert (
            "org.gnome.desktop.interface", "color-scheme",
            cfg.dark_color_scheme,
        ) in keys
        assert (
            "org.gnome.shell.extensions.user-theme", "name",
            cfg.dark_shell_theme,
        ) in keys

    def test_no_exception_if_shell_fails(self, mocker):
        mocker.patch(
            "solaris.theme_engine._gsettings_set",
            side_effect=[True, True, False],
        )
        mocker.patch("solaris.theme_engine._apply_gtk4_theme")
        # Should not raise.
        theme_engine.apply_dark(SolarisConfig())


# ---------------------------------------------------------------------------
# get_current_mode
# ---------------------------------------------------------------------------


class TestGetCurrentMode:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("'prefer-light'", "light"),
            ("'prefer-dark'", "dark"),
            ("'default'", "light"),
            ("prefer-dark", "dark"),  # no quotes
        ],
    )
    def test_known_values(self, mocker, raw, expected):
        mocker.patch(
            "solaris.theme_engine._gsettings_get", return_value=raw
        )
        assert theme_engine.get_current_mode() == expected

    def test_unknown_value_returns_unknown(self, mocker):
        mocker.patch(
            "solaris.theme_engine._gsettings_get", return_value="'something-weird'"
        )
        assert theme_engine.get_current_mode() == "unknown"

    def test_none_returns_unknown(self, mocker):
        mocker.patch("solaris.theme_engine._gsettings_get", return_value=None)
        assert theme_engine.get_current_mode() == "unknown"


# ---------------------------------------------------------------------------
# scan_themes
# ---------------------------------------------------------------------------


class TestScanThemes:
    def test_returns_sorted_matching_themes(self, tmp_path, monkeypatch):
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        for name in ("Colloid-Light", "Colloid-Dark", "Adwaita", "Yaru"):
            (themes_dir / name).mkdir()
        # A file (not a directory) that matches the prefix — should be skipped.
        (themes_dir / "Colloid-not-a-dir").touch()

        monkeypatch.setattr(theme_engine, "THEME_SCAN_PATH", themes_dir)

        result = theme_engine.scan_themes("Colloid")
        assert result == ["Colloid-Dark", "Colloid-Light"]

    def test_empty_prefix_returns_all_directories(self, tmp_path, monkeypatch):
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        for name in ("A", "B", "C"):
            (themes_dir / name).mkdir()

        monkeypatch.setattr(theme_engine, "THEME_SCAN_PATH", themes_dir)
        result = theme_engine.scan_themes("")
        assert result == ["A", "B", "C"]

    def test_missing_directory_returns_empty(self, tmp_path, monkeypatch):
        missing = tmp_path / "does-not-exist"
        monkeypatch.setattr(theme_engine, "THEME_SCAN_PATH", missing)
        assert theme_engine.scan_themes() == []

    def test_no_matches_returns_empty(self, tmp_path, monkeypatch):
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        (themes_dir / "Adwaita").mkdir()

        monkeypatch.setattr(theme_engine, "THEME_SCAN_PATH", themes_dir)
        assert theme_engine.scan_themes("Colloid") == []


# ---------------------------------------------------------------------------
# _apply_gtk4_theme
# ---------------------------------------------------------------------------


class TestApplyGtk4Theme:
    def test_symlinks_assets_and_css_from_user_themes(self, tmp_path, monkeypatch):
        """When the theme exists under ~/.themes, files are symlinked into ~/.config."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        # Build a fake ~/.themes/My-Theme/gtk-4.0 layout
        theme_root = fake_home / ".themes" / "My-Theme" / "gtk-4.0"
        theme_root.mkdir(parents=True)
        (theme_root / "assets").mkdir()
        (theme_root / "gtk.css").write_text("/* light */")
        (theme_root / "gtk-dark.css").write_text("/* dark */")

        theme_engine._apply_gtk4_theme("My-Theme")

        gtk4_dir = fake_home / ".config" / "gtk-4.0"
        assert (gtk4_dir / "assets").is_symlink()
        assert (gtk4_dir / "gtk.css").is_symlink()
        assert (gtk4_dir / "gtk-dark.css").is_symlink()
        assert (gtk4_dir / "gtk.css").read_text() == "/* light */"

    def test_no_op_when_theme_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            Path, "home", classmethod(lambda cls: tmp_path / "home")
        )
        # The function should silently return — no exceptions.
        theme_engine._apply_gtk4_theme("Nonexistent-Theme-12345")

    def test_replaces_existing_wrong_symlinks(self, tmp_path, monkeypatch):
        """When existing symlinks point to the wrong target, they are replaced."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        # Set up old wrong-target symlinks.
        old_theme = fake_home / ".themes" / "Old-Theme" / "gtk-4.0"
        old_theme.mkdir(parents=True)
        (old_theme / "gtk.css").write_text("/* old */")

        gtk4_dir = fake_home / ".config" / "gtk-4.0"
        gtk4_dir.mkdir(parents=True)
        (gtk4_dir / "gtk.css").symlink_to(old_theme / "gtk.css")

        # New theme.
        new_theme = fake_home / ".themes" / "New-Theme" / "gtk-4.0"
        new_theme.mkdir(parents=True)
        (new_theme / "gtk.css").write_text("/* new */")

        theme_engine._apply_gtk4_theme("New-Theme")

        assert (gtk4_dir / "gtk.css").read_text() == "/* new */"

    def test_idempotent_when_symlinks_already_correct(
        self, tmp_path, monkeypatch
    ):
        """Calling twice with the same theme should be a no-op the second time."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        theme_root = fake_home / ".themes" / "MyT" / "gtk-4.0"
        theme_root.mkdir(parents=True)
        (theme_root / "gtk.css").write_text("/* light */")

        theme_engine._apply_gtk4_theme("MyT")
        link_before = (fake_home / ".config" / "gtk-4.0" / "gtk.css").lstat()

        theme_engine._apply_gtk4_theme("MyT")  # second call
        link_after = (fake_home / ".config" / "gtk-4.0" / "gtk.css").lstat()

        # Inode unchanged — the function detected the symlink is correct.
        assert link_before.st_ino == link_after.st_ino
