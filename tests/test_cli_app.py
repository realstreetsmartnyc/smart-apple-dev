"""Tests for smartapple.cli.app module."""

import json
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from click.testing import CliRunner

from smartapple.cli.app import (
    _sanitize_bundle_id,
    _get_click,
    create_cli,
    cli as cli_entrypoint,
)
from smartapple.core.sdk import SdkInfo, SdkError


def test_sanitize_bundle_id():
    assert _sanitize_bundle_id("my-cool-app") == "my.cool.app"
    assert _sanitize_bundle_id("app") == "app"


def test_get_click():
    click_mod = _get_click()
    assert click_mod is not None


def test_cli_version():
    runner = CliRunner()
    cli = create_cli()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "1.0.2" in result.output


def test_cli_help():
    runner = CliRunner()
    cli = create_cli()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "smart-apple-dev" in result.output


def test_info_command(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.find_project_root", return_value=tmp_path):
        with patch(
            "smartapple.cli.app.list_installed_sdks",
            return_value=[
                SdkInfo(
                    version="18.0",
                    platform="iphoneos",
                    path=tmp_path / "sdk",
                )
            ],
        ):
            result = runner.invoke(cli, ["info"])
            assert result.exit_code == 0
            assert "smart-apple-dev info" in result.output
            assert "iphoneos 18.0" in result.output


def test_info_command_no_sdks():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.list_installed_sdks", return_value=[]):
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "No SDKs installed" in result.output


def test_check_command():
    runner = CliRunner()
    cli = create_cli()
    mock_orch = MagicMock()
    mock_orch.list_backends.return_value = ["swift"]
    mock_orch.check_backend_availability.return_value = {
        "checks": {"swiftc": {"available": True, "path": "/usr/bin/swiftc"}}
    }
    with patch("smartapple.cli.app.BuildOrchestrator", return_value=mock_orch):
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0
        assert "Backend availability" in result.output
        assert "swiftc: OK" in result.output


def test_doctor_command_json():
    runner = CliRunner()
    cli = create_cli()
    mock_report = MagicMock()
    mock_report.platform = "linux"
    mock_report.arch = "x86_64"
    mock_report.all_ok = True
    mock_report.sdk_count = 1
    mock_report.device_count = 0
    mock_report.checks = []
    mock_report.missing_required = []
    mock_report.missing_optional = []

    with patch("smartapple.doctor.run_checks", return_value=mock_report):
        result = runner.invoke(cli, ["doctor", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["platform"] == "linux"
        assert data["all_ok"] is True


def test_doctor_command_auto_install():
    runner = CliRunner()
    cli = create_cli()
    mock_report = MagicMock()
    mock_report.all_ok = True
    mock_report.checks = []
    mock_report.missing_required = []
    mock_report.missing_optional = []

    with patch("smartapple.doctor.run_checks", return_value=mock_report):
        with patch("smartapple.doctor.install_all", return_value=2):
            with patch("smartapple.doctor.print_report"):
                result = runner.invoke(cli, ["doctor", "--install"])
                assert result.exit_code == 0
                assert "Installed 2 tool(s)." in result.output


def test_devices_command():
    runner = CliRunner()
    cli = create_cli()

    mock_ios_dev = MagicMock()
    mock_ios_dev.udid = "1234-5678"
    mock_ios_dev.name = "My iPhone"
    mock_ios_dev.product = "iPhone 15"
    mock_ios_dev.ios_version = "17.0"

    mock_android_dev = MagicMock()
    mock_android_dev.serial = "emulator-5554"
    mock_android_dev.model = "Pixel_4"
    mock_android_dev.product = "sdk_gphone64_x86_64"
    mock_android_dev.state = "device"

    with patch("smartapple.cli.app.list_devices", return_value=[mock_ios_dev]):
        with patch("smartapple.device.list_android_devices", return_value=[mock_android_dev]):
            result = runner.invoke(cli, ["devices", "--platform", "all"])
            assert result.exit_code == 0
            assert "1234-5678" in result.output
            assert "emulator-5554" in result.output


def test_devices_command_none_found():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.list_devices", return_value=[]):
        with patch("smartapple.device.list_android_devices", return_value=[]):
            result = runner.invoke(cli, ["devices", "--platform", "ios"])
            assert result.exit_code == 0
            assert "No iOS devices found" in result.output

            result = runner.invoke(cli, ["devices", "--platform", "android"])
            assert result.exit_code == 0
            assert "No Android devices found" in result.output


def test_sdk_list_command():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.list_installed_sdks", return_value=[]):
        result = runner.invoke(cli, ["sdk", "list"])
        assert result.exit_code == 0
        assert "No SDKs installed" in result.output

    with patch(
        "smartapple.cli.app.list_installed_sdks",
        return_value=[SdkInfo("14.0", "macosx", Path("/tmp/mac"))],
    ):
        result = runner.invoke(cli, ["sdk", "list"])
        assert result.exit_code == 0
        assert "macosx 14.0" in result.output


def test_sdk_install_command():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.install_sdk") as mock_install:
        result = runner.invoke(cli, ["sdk", "install", "--platform", "iphoneos", "--version", "18.0"])
        assert result.exit_code == 0
        assert "Installed SDK iphoneos 18.0" in result.output
        mock_install.assert_called_once_with("iphoneos", "18.0")


def test_sdk_install_invalid_version():
    runner = CliRunner()
    cli = create_cli()
    result = runner.invoke(cli, ["sdk", "install", "--platform", "iphoneos", "--version", "99.0"])
    assert result.exit_code == 1
    assert "Available versions" in result.output


def test_sdk_install_error():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.install_sdk", side_effect=SdkError("Download failed")):
        result = runner.invoke(cli, ["sdk", "install", "--platform", "iphoneos", "--version", "18.0"])
        assert result.exit_code == 1
        assert "Download failed" in result.output


def test_sdk_extract_not_macos():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.get_platform", return_value="linux"):
        result = runner.invoke(cli, ["sdk", "extract"])
        assert result.exit_code == 1
        assert "must be run on macOS" in result.output


def test_sdk_extract_macos_success():
    runner = CliRunner()
    cli = create_cli()
    mock_info = MagicMock()
    mock_info.path = "/tmp/iphoneos18.0.sdk.tar.xz"
    with patch("smartapple.cli.app.get_platform", return_value="macos"):
        with patch("smartapple.core.sdk.extract_sdk_from_macos", return_value=mock_info):
            result = runner.invoke(cli, ["sdk", "extract"])
            assert result.exit_code == 0
            assert "Extracted: /tmp/iphoneos18.0.sdk.tar.xz" in result.output


def test_xtool_status_command():
    runner = CliRunner()
    cli = create_cli()

    mock_status = MagicMock()
    mock_status.platform = "linux"
    mock_status.swift_installed = True
    mock_status.swift_version = "5.9"
    mock_status.swift_path = "/usr/bin/swift"
    mock_status.xtool_cloned = True
    mock_status.xtool_built = True
    mock_status.xtool_path = "/usr/bin/xtool"
    mock_status.on_path = True
    mock_status.notes = ["Sample note"]
    mock_status.is_ready.return_value = True
    mock_status.to_dict.return_value = {"platform": "linux"}

    with patch("smartapple.xtool_env.xtool_status", return_value=mock_status):
        result = runner.invoke(cli, ["xtool", "status"])
        assert result.exit_code == 0
        assert "xtool is ready" in result.output

        result_json = runner.invoke(cli, ["xtool", "status", "--json"])
        assert result_json.exit_code == 0
        assert '"platform": "linux"' in result_json.output


def test_xtool_install_command():
    runner = CliRunner()
    cli = create_cli()

    mock_status = MagicMock()
    mock_status.is_ready.return_value = False

    with patch("smartapple.xtool_env.xtool_status", return_value=mock_status):
        with patch("smartapple.xtool_env.xtool_install", return_value=mock_status) as mock_inst:
            result = runner.invoke(cli, ["xtool", "install", "-y"])
            assert result.exit_code == 0
            assert "xtool installed" in result.output
            mock_inst.assert_called_once()


def test_xtool_install_aborted():
    runner = CliRunner()
    cli = create_cli()
    mock_status = MagicMock()
    mock_status.is_ready.return_value = False

    with patch("smartapple.xtool_env.xtool_status", return_value=mock_status):
        result = runner.invoke(cli, ["xtool", "install"], input="n\n")
        assert result.exit_code == 1
        assert "aborted by user" in result.output


def test_xtool_uninstall_command():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.xtool_env.xtool_uninstall") as mock_uninst:
        result = runner.invoke(cli, ["xtool", "uninstall", "-y"])
        assert result.exit_code == 0
        assert "xtool removed" in result.output
        mock_uninst.assert_called_once()


def test_xtool_verify_not_ready():
    runner = CliRunner()
    cli = create_cli()
    mock_status = MagicMock()
    mock_status.is_ready.return_value = False
    with patch("smartapple.xtool_env.xtool_status", return_value=mock_status):
        result = runner.invoke(cli, ["xtool", "verify"])
        assert result.exit_code == 1
        assert "xtool not ready" in result.output


def test_provider_list_and_default():
    runner = CliRunner()
    cli = create_cli()
    result = runner.invoke(cli, ["provider", "list"])
    assert result.exit_code == 0
    assert "Build providers" in result.output

    result_def = runner.invoke(cli, ["provider", "default"])
    assert result_def.exit_code == 0
    assert "Default: local" in result_def.output


def test_provider_instance_management():
    runner = CliRunner()
    cli = create_cli()

    # Invalid name (no colon)
    res_bad = runner.invoke(cli, ["provider", "add", "invalidname"])
    assert res_bad.exit_code == 1

    # Unknown base provider
    res_unknown = runner.invoke(cli, ["provider", "add", "unknownbase:label"])
    assert res_unknown.exit_code == 1

    # Valid add
    with patch("smartapple.agent.llm.set_instance_config") as mock_set:
        with patch("smartapple.agent.llm.list_named_instances", return_value={}):
            res_add = runner.invoke(
                cli,
                [
                    "provider",
                    "add",
                    "custom:mytest",
                    "--base-url",
                    "https://api.example.com/v1",
                    "--api-key",
                    "secret",
                ],
            )
            assert res_add.exit_code == 0
            assert "Saved: custom:mytest" in res_add.output
            mock_set.assert_called_once()

    # List instances
    with patch(
        "smartapple.agent.llm.list_named_instances",
        return_value={"custom:mytest": {"base_url": "https://api.example.com/v1"}},
    ):
        res_list = runner.invoke(cli, ["provider", "list-instances"])
        assert res_list.exit_code == 0
        assert "custom:mytest" in res_list.output

    # Delete instance
    with patch("smartapple.agent.llm.delete_instance_config") as mock_del:
        with patch(
            "smartapple.agent.llm.list_named_instances",
            return_value={"custom:mytest": {}},
        ):
            res_del = runner.invoke(cli, ["provider", "del", "custom:mytest"])
            assert res_del.exit_code == 0
            assert "Deleted: custom:mytest" in res_del.output
            mock_del.assert_called_once()


def test_agent_provider_list():
    runner = CliRunner()
    cli = create_cli()
    result = runner.invoke(cli, ["agent", "--provider", "list"])
    assert result.exit_code == 0
    assert "Available LLM providers:" in result.output


def test_agent_missing_plan_file():
    runner = CliRunner()
    cli = create_cli()
    result = runner.invoke(cli, ["agent", "--plan", "/nonexistent/plan.json"])
    assert result.exit_code == 1
    assert "plan file /nonexistent/plan.json not found" in result.output


def test_init_command_existing_dir(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("existing").mkdir()
        result = runner.invoke(cli, ["init", "existing"])
        assert result.exit_code == 1
        assert "already exists" in result.output


def test_init_command_invalid_language(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["init", "myapp", "--lang", "python"])
        assert result.exit_code != 0
        assert "Invalid value for '--lang'" in result.output or "invalid choice" in result.output.lower()


def test_build_no_config():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.find_project_root", return_value=None):
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 1
        assert "No smartapple.toml found" in result.output


def test_build_provider_unavailable(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    mock_prov = MagicMock()
    mock_prov.name = "custom_prov"
    mock_prov.is_available.return_value = (False, "Missing tool")

    with patch("smartapple.cli.app.find_project_root", return_value=tmp_path):
        with patch("smartapple.cli.app.load_config"):
            with patch("smartapple.build.provider.get_provider", return_value=mock_prov):
                result = runner.invoke(cli, ["build"])
                assert result.exit_code == 1
                assert "Provider 'custom_prov' not available: Missing tool" in result.output


def test_build_success(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    mock_prov = MagicMock()
    mock_prov.name = "local"
    mock_prov.is_available.return_value = (True, "")
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.artifact = tmp_path / "App.app"
    mock_result.duration_seconds = 1.2
    mock_result.metadata = {"language": "swift"}
    mock_prov.build.return_value = mock_result

    mock_cfg = MagicMock()
    mock_cfg.name = "TestApp"

    with patch("smartapple.cli.app.find_project_root", return_value=tmp_path):
        with patch("smartapple.cli.app.load_config", return_value=mock_cfg):
            with patch("smartapple.build.provider.get_provider", return_value=mock_prov):
                result = runner.invoke(cli, ["build"])
                assert result.exit_code == 0
                assert "Build succeeded" in result.output


def test_build_failure(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    mock_prov = MagicMock()
    mock_prov.name = "local"
    mock_prov.is_available.return_value = (True, "")
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.errors = ["Compilation failed", "ANDROID SDK missing"]
    mock_prov.build.return_value = mock_result

    mock_cfg = MagicMock()
    mock_cfg.name = "TestApp"

    with patch("smartapple.cli.app.find_project_root", return_value=tmp_path):
        with patch("smartapple.cli.app.load_config", return_value=mock_cfg):
            with patch("smartapple.build.provider.get_provider", return_value=mock_prov):
                result = runner.invoke(cli, ["build"])
                assert result.exit_code == 1
                assert "Build failed" in result.output


def test_sign_no_config():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.find_project_root", return_value=None):
        result = runner.invoke(cli, ["sign"])
        assert result.exit_code == 1
        assert "No smartapple.toml found" in result.output


def test_sign_build_failure(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    mock_cfg = MagicMock()
    mock_cfg.target = "ios"

    mock_orch = MagicMock()
    mock_build_res = MagicMock()
    mock_build_res.success = False
    mock_orch.build.return_value = mock_build_res

    with patch("smartapple.cli.app.find_project_root", return_value=tmp_path):
        with patch("smartapple.cli.app.load_config", return_value=mock_cfg):
            with patch("smartapple.cli.app.BuildOrchestrator", return_value=mock_orch):
                result = runner.invoke(cli, ["sign"])
                assert result.exit_code == 1
                assert "Build failed, cannot sign" in result.output


def test_notarize_no_config():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.find_project_root", return_value=None):
        result = runner.invoke(cli, ["notarize"])
        assert result.exit_code == 1
        assert "No smartapple.toml found" in result.output


def test_notarize_candidate_not_found(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    mock_cfg = MagicMock()
    mock_cfg.target = "macos"
    mock_cfg.name = "TestApp"

    with patch("smartapple.cli.app.find_project_root", return_value=tmp_path):
        with patch("smartapple.cli.app.load_config", return_value=mock_cfg):
            result = runner.invoke(cli, ["notarize"])
            assert result.exit_code == 1
            assert "Could not find" in result.output


def test_install_no_config():
    runner = CliRunner()
    cli = create_cli()
    with patch("smartapple.cli.app.find_project_root", return_value=None):
        result = runner.invoke(cli, ["install"])
        assert result.exit_code == 1
        assert "No smartapple.toml found" in result.output


def test_install_apk_success(tmp_path):
    runner = CliRunner()
    cli = create_cli()
    apk_file = tmp_path / "test.apk"
    apk_file.write_text("fake apk")

    mock_dev = MagicMock()
    mock_dev.serial = "emulator-5554"

    with patch("smartapple.device.list_android_devices", return_value=[mock_dev]):
        with patch("smartapple.device.install_apk", return_value=True):
            result = runner.invoke(cli, ["install", "--apk", str(apk_file)])
            assert result.exit_code == 0
            assert "Installed to emulator-5554" in result.output


def test_cli_entrypoint(tmp_path):
    with patch("smartapple.cli.app.create_cli") as mock_create_cli:
        mock_group = MagicMock()
        mock_create_cli.return_value = mock_group
        cli_entrypoint(["--version"])
        mock_group.assert_called_once()
