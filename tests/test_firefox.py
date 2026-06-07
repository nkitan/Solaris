"""Tests for solaris.firefox — sample CSS strings, profile discovery, marker injection."""

from __future__ import annotations

from pathlib import Path

import pytest

from solaris import firefox


# ---------------------------------------------------------------------------
# Marker / block injection
# ---------------------------------------------------------------------------


class TestBuildReplacementBlock:
    def test_light_block_contains_light_hexcodes(self):
        block = firefox._build_replacement_block("light")
        assert "#ffffff" in block
        assert "#000000" in block
        assert firefox.MARKER_START in block
        assert firefox.MARKER_END in block

    def test_dark_block_contains_dark_hexcodes(self):
        block = firefox._build_replacement_block("dark")
        assert "#282828" in block
        assert "#ebdbb2" in block

    def test_invalid_mode_falls_back_to_dark_branch(self):
        # The function falls into the else branch — dark colours.
        block = firefox._build_replacement_block("anything-else")
        assert "#282828" in block


class TestInjectBlock:
    def test_appends_when_no_markers(self):
        existing = "/* user styles */\n.foo { color: red; }"
        new_block = firefox._build_replacement_block("light")
        result = firefox._inject_block(existing, new_block)
        assert result.startswith(existing)
        assert firefox.MARKER_START in result
        assert firefox.MARKER_END in result

    def test_appends_with_separator_when_existing_content_present(self):
        existing = ".foo { color: red; }"
        new_block = firefox._build_replacement_block("light")
        result = firefox._inject_block(existing, new_block)
        assert "\n\n" in result  # separator added

    def test_no_separator_when_existing_is_empty(self):
        existing = ""
        new_block = firefox._build_replacement_block("dark")
        result = firefox._inject_block(existing, new_block)
        assert result.startswith(firefox.MARKER_START)

    def test_replaces_between_markers(self):
        existing = (
            "/* prologue */\n"
            f"{firefox.MARKER_START}\n"
            ":root { --solaris-bg: #ffffff; }\n"
            f"{firefox.MARKER_END}\n"
            "/* epilogue */\n"
        )
        new_block = firefox._build_replacement_block("dark")
        result = firefox._inject_block(existing, new_block)

        assert "#282828" in result
        assert "#ffffff" not in result
        assert "/* prologue */" in result
        assert "/* epilogue */" in result

    def test_only_one_marker_block_after_replace(self):
        existing = (
            f"{firefox.MARKER_START}\nfoo\n{firefox.MARKER_END}\n"
        )
        new_block = firefox._build_replacement_block("light")
        result = firefox._inject_block(existing, new_block)

        assert result.count(firefox.MARKER_START) == 1
        assert result.count(firefox.MARKER_END) == 1

    def test_handles_end_marker_before_start_as_no_markers(self):
        """If markers are inverted, treat as no-marker and append."""
        existing = f"{firefox.MARKER_END}\nfoo\n{firefox.MARKER_START}\n"
        new_block = firefox._build_replacement_block("light")
        result = firefox._inject_block(existing, new_block)

        # The function appends rather than replaces in this odd case.
        assert result.startswith(existing.rstrip())


# ---------------------------------------------------------------------------
# find_active_profile
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_firefox_dir(tmp_path, monkeypatch):
    """Create a fake ~/.mozilla/firefox layout and redirect Path.home()."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    firefox_dir = fake_home / ".mozilla" / "firefox"
    firefox_dir.mkdir(parents=True)
    return firefox_dir


class TestFindActiveProfile:
    def test_returns_none_when_no_profiles_ini(self, fake_firefox_dir):
        assert firefox.find_active_profile() is None

    def test_returns_default_profile_when_marked(self, fake_firefox_dir):
        profile_dir = fake_firefox_dir / "abc.default-release"
        profile_dir.mkdir()

        (fake_firefox_dir / "profiles.ini").write_text(
            "[Profile0]\n"
            "Name=default-release\n"
            "IsRelative=1\n"
            "Path=abc.default-release\n"
            "Default=1\n"
            "\n"
            "[Profile1]\n"
            "Name=dev\n"
            "IsRelative=1\n"
            "Path=xyz.dev\n"
        )

        result = firefox.find_active_profile()
        assert result == profile_dir.resolve() or result == profile_dir

    def test_returns_fallback_when_no_default_marked(self, fake_firefox_dir):
        profile_dir = fake_firefox_dir / "abc.profile"
        profile_dir.mkdir()
        (fake_firefox_dir / "profiles.ini").write_text(
            "[Profile0]\n"
            "Name=default\n"
            "IsRelative=1\n"
            "Path=abc.profile\n"
        )

        result = firefox.find_active_profile()
        assert str(result).endswith("abc.profile")

    def test_returns_none_when_profile_dir_missing(self, fake_firefox_dir):
        (fake_firefox_dir / "profiles.ini").write_text(
            "[Profile0]\n"
            "Name=ghost\n"
            "IsRelative=1\n"
            "Path=does-not-exist\n"
            "Default=1\n"
        )
        assert firefox.find_active_profile() is None

    def test_handles_absolute_paths(self, fake_firefox_dir, tmp_path):
        external_profile = tmp_path / "external.profile"
        external_profile.mkdir()

        (fake_firefox_dir / "profiles.ini").write_text(
            "[Profile0]\n"
            "Name=external\n"
            "IsRelative=0\n"
            f"Path={external_profile}\n"
            "Default=1\n"
        )

        result = firefox.find_active_profile()
        assert result == external_profile

    def test_finds_in_xdg_config_when_dot_mozilla_missing(
        self, tmp_path, monkeypatch
    ):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        firefox_xdg = fake_home / ".config" / "mozilla" / "firefox"
        firefox_xdg.mkdir(parents=True)
        profile = firefox_xdg / "abc.default"
        profile.mkdir()

        (firefox_xdg / "profiles.ini").write_text(
            "[Profile0]\n"
            "Name=default\n"
            "IsRelative=1\n"
            "Path=abc.default\n"
            "Default=1\n"
        )

        assert firefox.find_active_profile() == profile


# ---------------------------------------------------------------------------
# ensure_chrome_dir
# ---------------------------------------------------------------------------


class TestEnsureChromeDir:
    def test_creates_chrome_dir(self, tmp_path):
        profile = tmp_path / "profile"
        profile.mkdir()

        chrome_dir = firefox.ensure_chrome_dir(profile)
        assert chrome_dir.is_dir()
        assert chrome_dir.name == "chrome"

    def test_returns_existing_chrome_dir(self, tmp_path):
        profile = tmp_path / "profile"
        chrome = profile / "chrome"
        chrome.mkdir(parents=True)

        result = firefox.ensure_chrome_dir(profile)
        assert result == chrome


# ---------------------------------------------------------------------------
# apply_theme (end-to-end with sample CSS files)
# ---------------------------------------------------------------------------


class TestApplyTheme:
    def test_invalid_mode_returns_false(self):
        assert firefox.apply_theme("amber") is False

    def test_returns_false_when_no_profile(self, mocker):
        mocker.patch(
            "solaris.firefox.find_active_profile", return_value=None
        )
        assert firefox.apply_theme("light") is False

    def test_creates_userchrome_when_missing(self, tmp_path, mocker):
        profile = tmp_path / "profile"
        profile.mkdir()
        mocker.patch(
            "solaris.firefox.find_active_profile", return_value=profile
        )

        result = firefox.apply_theme("dark")
        assert result is True

        css = (profile / "chrome" / "userChrome.css").read_text()
        assert firefox.MARKER_START in css
        assert "#282828" in css

    def test_updates_existing_block(self, tmp_path, mocker):
        profile = tmp_path / "profile"
        chrome = profile / "chrome"
        chrome.mkdir(parents=True)
        # Existing file with light values.
        (chrome / "userChrome.css").write_text(
            "/* user rules */\n"
            f"{firefox.MARKER_START}\n"
            ":root { --solaris-bg: #ffffff; --solaris-text: #000000; }\n"
            f"{firefox.MARKER_END}\n"
        )
        mocker.patch(
            "solaris.firefox.find_active_profile", return_value=profile
        )

        assert firefox.apply_theme("dark") is True

        css = (chrome / "userChrome.css").read_text()
        assert "#282828" in css
        assert "#ffffff" not in css
        assert "/* user rules */" in css

    def test_creates_backup(self, tmp_path, mocker):
        profile = tmp_path / "profile"
        chrome = profile / "chrome"
        chrome.mkdir(parents=True)
        (chrome / "userChrome.css").write_text("/* original */\n")
        mocker.patch(
            "solaris.firefox.find_active_profile", return_value=profile
        )

        firefox.apply_theme("light")
        assert (chrome / "userChrome.css.bak").exists()
        assert (chrome / "userChrome.css.bak").read_text() == "/* original */\n"

    def test_no_write_when_already_up_to_date(self, tmp_path, mocker):
        profile = tmp_path / "profile"
        chrome = profile / "chrome"
        chrome.mkdir(parents=True)
        mocker.patch(
            "solaris.firefox.find_active_profile", return_value=profile
        )
        # First call writes; second call should be a no-op.
        firefox.apply_theme("light")
        first_mtime = (chrome / "userChrome.css").stat().st_mtime_ns

        firefox.apply_theme("light")
        second_mtime = (chrome / "userChrome.css").stat().st_mtime_ns
        # No backup should be created the second time either.
        assert first_mtime == second_mtime

    def test_returns_false_on_write_failure(self, tmp_path, mocker):
        profile = tmp_path / "profile"
        profile.mkdir()
        mocker.patch(
            "solaris.firefox.find_active_profile", return_value=profile
        )
        # Force write to fail by mocking write_text.
        mocker.patch.object(
            Path, "write_text", side_effect=OSError("permission denied")
        )

        assert firefox.apply_theme("light") is False
