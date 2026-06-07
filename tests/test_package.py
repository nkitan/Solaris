"""Tests for solaris package metadata."""

from __future__ import annotations

import re

import solaris


class TestPackageMetadata:
    def test_version_exists(self):
        assert hasattr(solaris, "__version__")
        assert isinstance(solaris.__version__, str)

    def test_version_format(self):
        # Semantic-versioning-like check (MAJOR.MINOR.PATCH).
        assert re.match(r"^\d+\.\d+\.\d+", solaris.__version__)

    def test_app_id_exists(self):
        assert hasattr(solaris, "__app_id__")
        assert solaris.__app_id__ == "io.github.solaris"
