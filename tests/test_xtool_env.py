"""Tests for xtool_env module — mocked to avoid 600MB Swift download."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from smartapple.xtool_env import (
    xtool_status,
    XtoolStatus,
    _install_root,
    _swift_install_path,
    _xtool_install_path,
    _swift_bin,
    _xtool_bin,
    _is_on_path,
    SWIFT_VERSION,
    XTOOL_REPO,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _mock_status(
    swift_installed: bool = False,
    swift_path: str | None = None,
    swift_version: str | None = None,
    xtool_cloned: bool = False,
    xtool_built: bool = False,
    xtool_path: str | None = None,
    on_path: bool = False,
    platform: str = "linux",
    notes: list[str] | None = None,
) -> XtoolStatus:
    """Build a XtoolStatus with the given fields."""
    s = XtoolStatus(platform=platform)
    s.swift_installed = swift_installed
    s.swift_path = swift_path
    s.swift_version = swift_version
    s.xtool_cloned = xtool_cloned
    s.xtool_built = xtool_built
    s.xtool_path = xtool_path
    s.on_path = on_path
    if notes is not None:
        s.notes.extend(notes)
    return s


# -------------------------------------------------------------------
# XtoolStatus dataclass
# -------------------------------------------------------------------

class TestXtoolStatus:
    def test_to_dict_returns_all_fields(self):
        s = _mock_status(
            swift_installed=True,
            swift_path="/home/user/.smart-apple-dev/swift/bin/swift",
            swift_version="swift-6.1.3-RELEASE",
            xtool_cloned=True,
            xtool_built=True,
            xtool_path="/home/user/.smart-apple-dev/xtool/.build/release/xtool",
            on_path=True,
            notes=["all good"],
        )
        d = s.to_dict()
        assert d["platform"] == "linux"
        assert d["swift_installed"] is True
        assert d["swift_version"] == "swift-6.1.3-RELEASE"
        assert d["xtool_built"] is True
        assert d["on_path"] is True
        assert "all good" in d["notes"]

    def test_is_ready_true(self):
        s = _mock_status(swift_installed=True, xtool_built=True, on_path=True)
        assert s.is_ready() is True

    def test_is_ready_false_missing_swift(self):
        s = _mock_status(swift_installed=False, xtool_built=True, on_path=False)
        assert s.is_ready() is False

    def test_is_ready_false_missing_xtool(self):
        s = _mock_status(swift_installed=True, xtool_built=False, on_path=False)
        assert s.is_ready() is False


# -------------------------------------------------------------------
# Path helpers
# -------------------------------------------------------------------

class TestInstallRoot:
    def test_install_root_defaults_to_home_dot_smart_apple_dev(self, monkeypatch, tmp_path):
        # Override Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # Override statvfs to report >= 5 GB free
        class MockStatVfs:
            f_bavail = 10_000_000
            f_frsize = 4096
        monkeypatch.setattr(os, "statvfs", lambda p: MockStatVfs())
        monkeypatch.delenv("SAD_XTOOL_INSTALL_ROOT", raising=False)
        root = _install_root()
        assert root == tmp_path / ".smart-apple-dev"

    def test_install_root_respects_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SAD_XTOOL_INSTALL_ROOT", "/custom/path")
        root = _install_root()
        assert root == Path("/custom/path")


# -------------------------------------------------------------------
# xtool_status()
# -------------------------------------------------------------------

class TestXtoolStatusFunction:
    @patch("smartapple.xtool_env._swift_bin", return_value=None)
    @patch("smartapple.xtool_env._xtool_bin", return_value=None)
    @patch("smartapple.xtool_env._xtool_install_path")
    @patch("smartapple.xtool_env.get_platform")
    def test_status_no_swift_no_xtool(
        self, mock_platform, mock_xd, mock_xb, mock_sb
    ):
        mock_platform.return_value = "linux"
        mock_xd.return_value = Path("/home/user/.smart-apple-dev/xtool")
        s = xtool_status()
        assert s.platform == "linux"
        assert s.swift_installed is False
        assert s.xtool_cloned is False
        assert s.xtool_built is False
        assert s.on_path is False
        assert len(s.notes) >= 1  # Should mention Swift not installed

    @patch("smartapple.xtool_env._swift_bin")
    @patch("smartapple.xtool_env._xtool_bin", return_value=None)
    @patch("smartapple.xtool_env._xtool_install_path")
    @patch("smartapple.xtool_env.get_platform")
    def test_status_swift_installed_xtool_not_built(
        self, mock_platform, mock_xd, mock_xb, mock_sb
    ):
        mock_platform.return_value = "linux"
        mock_sb.return_value = Path("/swift/usr/bin/swift")
        mock_xd.return_value = Path("/xd")
        with patch("smartapple.xtool_env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="swift-6.1.3-RELEASE\nswift-6.1.3",
                stderr="",
            )
            s = xtool_status()
        assert s.swift_installed is True
        assert "6.1.3" in s.swift_version
        assert s.xtool_built is False

    @patch("smartapple.xtool_env._swift_bin")
    @patch("smartapple.xtool_env._xtool_bin")
    @patch("smartapple.xtool_env._xtool_install_path")
    @patch("smartapple.xtool_env.get_platform")
    def test_status_full_ready(
        self, mock_platform, mock_xd, mock_xb, mock_sb
    ):
        mock_platform.return_value = "linux"
        mock_sb.return_value = Path("/swift/usr/bin/swift")
        mock_xd.return_value = Path("/xd")
        mock_xb.return_value = Path("/xd/.build/release/xtool")
        with patch("smartapple.xtool_env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="swift-6.1.3-RELEASE\nswift-6.1.3",
                stderr="",
            )
            # Mock _is_on_path to return True (simulate tools on PATH)
            with patch("smartapple.xtool_env._is_on_path", return_value=True):
                s = xtool_status()
        assert s.swift_installed is True
        assert s.xtool_built is True
        assert s.is_ready() is True


# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

def test_swift_version_is_reasonable():
    assert SWIFT_VERSION.startswith("6.")
    assert len(SWIFT_VERSION.split(".")) >= 2


def test_xtool_repo_is_github():
    assert XTOOL_REPO.startswith("https://github.com/")
    assert "xtool" in XTOOL_REPO
