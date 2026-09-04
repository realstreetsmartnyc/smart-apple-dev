"""Tests for notarize module — mocked to avoid macOS-only notarytool."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import zipfile

import pytest

from smartapple.notarize import (
    notarize_app,
    NotarizeResult,
    _make_zip_for_notary,
    _remote_notarize,
)


# -------------------------------------------------------------------
# NotarizeResult dataclass
# -------------------------------------------------------------------

class TestNotarizeResult:
    def test_defaults(self):
        r = NotarizeResult(success=True)
        assert r.success is True
        assert r.artifact_path is None
        assert r.ticket_path is None
        assert r.output == ""
        assert r.warnings == []
        assert r.errors == []

    def test_to_dict_round_trip(self):
        r = NotarizeResult(
            success=True,
            artifact_path=Path("/tmp/My.app"),
            output="success",
            warnings=["a warning"],
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["artifact_path"] == "/tmp/My.app"
        assert d["output"] == "success"
        assert d["warnings"] == ["a warning"]
        assert d["errors"] == []

    def test_to_dict_with_errors(self):
        r = NotarizeResult(success=False, errors=["xcrun not found"])
        d = r.to_dict()
        assert d["success"] is False
        assert d["errors"] == ["xcrun not found"]


# -------------------------------------------------------------------
# _make_zip_for_notary
# -------------------------------------------------------------------

class TestMakeZipForNotary:
    def test_creates_zip(self, tmp_path):
        # Create a fake .app bundle
        app = tmp_path / "MyApp.app"
        (app / "Contents").mkdir(parents=True)
        (app / "Contents" / "Info.plist").write_text("<plist></plist>")
        (app / "Contents" / "MacOS").mkdir()
        (app / "Contents" / "MacOS" / "MyApp").write_text("binary")

        zip_path = tmp_path / "notary.zip"
        ok = _make_zip_for_notary(app, zip_path)
        assert ok is True
        assert zip_path.exists()

        # Verify zip contents
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            assert "MyApp.app/Contents/Info.plist" in names
            assert "MyApp.app/Contents/MacOS/MyApp" in names

    def test_overwrites_existing_zip(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        (app / "test.txt").write_text("v1")

        zip_path = tmp_path / "notary.zip"
        zip_path.write_text("old")  # Existing

        _make_zip_for_notary(app, zip_path)
        assert zip_path.exists()
        # Should be a valid zip now
        with zipfile.ZipFile(zip_path) as z:
            assert "MyApp.app/test.txt" in z.namelist()


# -------------------------------------------------------------------
# notarize_app
# -------------------------------------------------------------------

class TestNotarizeApp:
    def test_artifact_does_not_exist(self, tmp_path):
        r = notarize_app(str(tmp_path / "missing.app"))
        assert r.success is False
        assert "not found" in r.errors[0]

    def test_not_an_app_bundle(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        r = notarize_app(str(f))
        assert r.success is False
        assert "expected a .app" in r.errors[0]

    def test_linux_without_remote_fails(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        with patch("smartapple.notarize.get_platform", return_value="linux"):
            r = notarize_app(str(app))
        assert r.success is False
        assert "--remote" in str(r.errors) or "linux" in str(r.errors).lower()

    def test_macos_without_xcrun(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        with patch("smartapple.notarize.get_platform", return_value="macos"):
            with patch("smartapple.notarize.check_tool", return_value=None):
                r = notarize_app(str(app))
        assert r.success is False

    def test_macos_without_identity(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        (app / "Contents").mkdir()
        (app / "Contents" / "Info.plist").write_text("<plist/>")
        with patch("smartapple.notarize.get_platform", return_value="macos"):
            with patch("smartapple.notarize.check_tool", return_value="/usr/bin/xcrun"):
                r = notarize_app(str(app), identity=None)
        assert r.success is False
        assert "--identity" in r.errors[0]

    def test_macos_notarytool_success(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        (app / "Contents").mkdir()
        (app / "Contents" / "Info.plist").write_text("<plist/>")
        with patch("smartapple.notarize.get_platform", return_value="macos"):
            with patch("smartapple.notarize.check_tool", return_value="/usr/bin/xcrun"):
                with patch("smartapple.notarize.subprocess.run") as mock_run:
                    # First call: notarytool submit; Second: stapler
                    mock_run.side_effect = [
                        MagicMock(returncode=0, stdout="notarized", stderr=""),
                        MagicMock(returncode=0, stdout="stapled", stderr=""),
                    ]
                    r = notarize_app(str(app), identity="MyProfile")
        assert r.success is True
        assert r.artifact_path == app
        assert r.errors == []
        assert r.warnings == []  # stapler succeeded

    def test_macos_notarytool_failure(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        (app / "Contents").mkdir()
        (app / "Contents" / "Info.plist").write_text("<plist/>")
        with patch("smartapple.notarize.get_platform", return_value="macos"):
            with patch("smartapple.notarize.check_tool", return_value="/usr/bin/xcrun"):
                with patch("smartapple.notarize.subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=1, stdout="", stderr="xcrun failed"
                    )
                    r = notarize_app(str(app), identity="MyProfile")
        assert r.success is False
        assert "notarytool failed" in r.errors[0]


# -------------------------------------------------------------------
# _remote_notarize
# -------------------------------------------------------------------

class TestRemoteNotarize:
    def test_remote_missing_identity(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        (app / "Contents").mkdir()
        (app / "Contents" / "Info.plist").write_text("<plist/>")
        with patch("smartapple.notarize.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            r = _remote_notarize(app, identity="", remote_host="user@mac", bundle_id="com.x.y")
        assert r.success is False
        assert "--identity" in r.errors[0] or "identity" in str(r.errors).lower()

    def test_remote_ssh_mkdir_fails(self, tmp_path):
        app = tmp_path / "MyApp.app"
        app.mkdir()
        (app / "Contents").mkdir()
        (app / "Contents" / "Info.plist").write_text("<plist/>")
        with patch("smartapple.notarize.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Permission denied")
            r = _remote_notarize(app, identity="MyProfile", remote_host="user@mac", bundle_id="com.x.y")
        assert r.success is False
        assert "ssh mkdir" in r.errors[0] or "ssh" in r.errors[0].lower()
