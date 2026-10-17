"""Tests for smartapple.store module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from smartapple.store import (
    AscResult,
    check_asc_availability,
    upload_to_app_store,
    submit_for_review,
)


class TestAscResult:
    def test_defaults(self):
        res = AscResult(success=True)
        assert res.success is True
        assert res.output == ""
        assert res.errors == []
        assert res.app_id is None

    def test_to_dict(self):
        res = AscResult(
            success=False,
            output="some output",
            errors=["an error"],
            app_id="123456",
        )
        d = res.to_dict()
        assert d == {
            "success": False,
            "output": "some output",
            "errors": ["an error"],
            "app_id": "123456",
        }


class TestCheckAscAvailability:
    def test_availability_all_installed(self):
        with patch("smartapple.store.check_tool", side_effect=lambda tool: f"/usr/local/bin/{tool}"):
            res = check_asc_availability()
            assert res == {
                "fastlane": True,
                "altool": True,
                "asc_api": True,
            }

    def test_availability_none_installed(self):
        with patch("smartapple.store.check_tool", return_value=None):
            res = check_asc_availability()
            assert res == {
                "fastlane": False,
                "altool": False,
                "asc_api": True,
            }


class TestUploadToAppStore:
    def test_upload_no_tools(self, tmp_path):
        ipa = tmp_path / "app.ipa"
        ipa.write_text("dummy ipa")
        with patch("smartapple.store.check_tool", return_value=None):
            res = upload_to_app_store(ipa, config={})
            assert res.success is False
            assert len(res.errors) == 1
            assert "No App Store Connect upload tool found" in res.errors[0]

    def test_upload_fastlane_success(self, tmp_path):
        ipa = tmp_path / "app.ipa"
        ipa.write_text("dummy ipa")

        def mock_check_tool(tool):
            if tool == "fastlane":
                return "/usr/local/bin/fastlane"
            return None

        with patch("smartapple.store.check_tool", side_effect=mock_check_tool):
            with patch("smartapple.store.run_cmd") as mock_run_cmd:
                mock_run_cmd.return_value = (0, "Fastlane succeeded", "")
                res = upload_to_app_store(
                    ipa,
                    config={},
                    username="user@example.com",
                    password="secretpassword",
                    app_specific_password="app-spec-pass",
                )

                assert res.success is True
                assert res.output == "Fastlane succeeded"
                assert res.errors == []

                # Verify run_cmd parameters
                mock_run_cmd.assert_called_once()
                args, kwargs = mock_run_cmd.call_args
                assert args[0] == ["fastlane", "upload_to_app_store"]
                assert kwargs["cwd"] == tmp_path / "fastlane"
                assert kwargs["env"] == {
                    "FASTLANE_USER": "user@example.com",
                    "FASTLANE_PASSWORD": "secretpassword",
                }
                assert kwargs["timeout"] == 600

                # Verify Fastfile content
                fastfile = tmp_path / "fastlane" / "Fastfile"
                assert fastfile.exists()
                fastfile_content = fastfile.read_text()
                assert f'ipa: "{ipa}"' in fastfile_content
                assert 'username: "user@example.com"' in fastfile_content
                assert 'app_specific_password: "app-spec-pass"' in fastfile_content

    def test_upload_fastlane_failure(self, tmp_path):
        ipa = tmp_path / "app.ipa"
        ipa.write_text("dummy ipa")

        with patch("smartapple.store.check_tool", side_effect=lambda tool: "/usr/bin/" + tool if tool == "fastlane" else None):
            with patch("smartapple.store.run_cmd", return_value=(1, "output logs", "Upload failed error")):
                res = upload_to_app_store(ipa, config={})
                assert res.success is False
                assert res.output == "output logs"
                assert res.errors == ["Upload failed error"]

    def test_upload_altool_success(self, tmp_path):
        ipa = tmp_path / "app.ipa"
        ipa.write_text("dummy ipa")

        def mock_check_tool(tool):
            if tool == "altool":
                return "/usr/bin/altool"
            return None

        with patch("smartapple.store.check_tool", side_effect=mock_check_tool):
            with patch("smartapple.store.run_cmd") as mock_run_cmd:
                mock_run_cmd.return_value = (0, "altool succeeded", "")
                res = upload_to_app_store(
                    ipa,
                    config={},
                    username="user@example.com",
                    app_specific_password="app-spec-pass",
                )

                assert res.success is True
                assert res.output == "altool succeeded"
                assert res.errors == []

                mock_run_cmd.assert_called_once_with(
                    ["altool", "--upload-app", "-f", str(ipa), "-u", "user@example.com", "-p", "app-spec-pass"],
                    timeout=600,
                )

    def test_upload_altool_failure(self, tmp_path):
        ipa = tmp_path / "app.ipa"
        ipa.write_text("dummy ipa")

        def mock_check_tool(tool):
            if tool == "altool":
                return "/usr/bin/altool"
            return None

        with patch("smartapple.store.check_tool", side_effect=mock_check_tool):
            with patch("smartapple.store.run_cmd", return_value=(1, "", "altool failed")):
                res = upload_to_app_store(ipa, config={})
                assert res.success is False
                assert res.errors == ["altool failed"]


class TestSubmitForReview:
    def test_submit_no_fastlane(self):
        with patch("smartapple.store.check_tool", return_value=None):
            res = submit_for_review("com.example.app")
            assert res.success is False
            assert len(res.errors) == 2
            assert "fastlane not found" in res.errors[0]

    def test_submit_success(self):
        with patch("smartapple.store.check_tool", return_value="/usr/local/bin/fastlane"):
            with patch("smartapple.store.run_cmd") as mock_run_cmd:
                mock_run_cmd.return_value = (0, "Submitted for review", "")
                res = submit_for_review(
                    app_id="123456789",
                    username="user@example.com",
                    password="secretpassword",
                    skip_build_processing=True,
                    platform="macos",
                )

                assert res.success is True
                assert res.output == "Submitted for review"
                assert res.app_id == "123456789"
                assert res.errors == []

                mock_run_cmd.assert_called_once()
                args, kwargs = mock_run_cmd.call_args
                assert args[0] == ["fastlane", "submit_for_review"]
                assert kwargs["env"] == {
                    "FASTLANE_USER": "user@example.com",
                    "FASTLANE_PASSWORD": "secretpassword",
                }
