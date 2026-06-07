"""Shared pytest fixtures for the Solaris test suite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_xdg_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect XDG_CONFIG_HOME to a temporary directory for the test.

    Patches both the environment variable AND the module-level
    `xdg.BaseDirectory.xdg_config_home` constant, since pyxdg caches
    the path at import time.
    """
    xdg_dir = tmp_path / "xdg-config"
    xdg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))

    # pyxdg snapshots XDG_CONFIG_HOME at import — patch the cached value too.
    from xdg import BaseDirectory
    monkeypatch.setattr(BaseDirectory, "xdg_config_home", str(xdg_dir))
    monkeypatch.setattr(
        BaseDirectory, "xdg_config_dirs", [str(xdg_dir), "/etc/xdg"]
    )
    return xdg_dir


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME to a temporary directory for the test."""
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return home_dir


@pytest.fixture
def isolated_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Combine HOME and XDG_CONFIG_HOME redirection for full isolation."""
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    xdg_dir = home_dir / ".config"
    xdg_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))

    from xdg import BaseDirectory
    monkeypatch.setattr(BaseDirectory, "xdg_config_home", str(xdg_dir))
    monkeypatch.setattr(
        BaseDirectory, "xdg_config_dirs", [str(xdg_dir), "/etc/xdg"]
    )
    return home_dir
