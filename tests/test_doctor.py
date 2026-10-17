"""Tests for doctor module — checking toolchain status and installer helpers."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from smartapple.doctor import (
    CheckResult,
    DoctorReport,
    _version_of,
    run_checks,
    print_report,
    _download_to,
    install_xtool,
    install_ldid,
    install_cctools,
    _is_apt_system,
    install_apt_pkgs,
    install_clang_via_apt,
    install_cmake_via_apt,
    install_lld_via_apt,
    install_libimobiledevice_via_apt,
    install_godot_export_templates,
    install_all,
)


class TestCheckResultAndDoctorReport:
    def test_check_result_to_dict(self):
        cr = CheckResult(
            name="clang",
            category="toolchain",
            available=True,
            path="/usr/bin/clang",
            required=True,
            install_hint="Install clang via apt",
        )
        d = cr.to_dict()
        assert d["name"] == "clang"
        assert d["category"] == "toolchain"
        assert d["available"] is True
        assert d["path"] == "/usr/bin/clang"
        assert d["required"] is True
        assert d["install_hint"] == "Install clang via apt"

    def test_doctor_report_properties(self):
        c1 = CheckResult("clang", "toolchain", available=True, required=True)
        c2 = CheckResult("cmake", "toolchain", available=False, required=False)
        c3 = CheckResult("make", "toolchain", available=False, required=True)

        rep = DoctorReport(platform="linux", arch="x86_64", checks=[c1, c2, c3])

        assert rep.missing_required == [c3]
        assert rep.missing_optional == [c2]
        assert rep.all_ok is False

        # If required is present
        rep.checks = [c1, c2]
        assert rep.all_ok is True


class TestVersionOf:
    @patch("subprocess.run")
    def test_version_of_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="clang version 14.0.0\nTarget: x86_64", stderr="")
        ver = _version_of("clang")
        assert ver == "clang version 14.0.0"

    @patch("subprocess.run", side_effect=Exception("error"))
    def test_version_of_exception(self, mock_run):
        ver = _version_of("clang")
        assert ver == ""


class TestRunChecks:
    @patch("smartapple.doctor.get_platform", return_value="linux")
    @patch("platform.machine", return_value="x86_64")
    @patch("smartapple.doctor.check_tool")
    @patch("smartapple.doctor.list_installed_sdks")
    @patch("smartapple.device.list_devices")
    def test_run_checks_success(
        self, mock_list_devices, mock_sdks, mock_check_tool, mock_machine, mock_platform
    ):
        mock_check_tool.side_effect = lambda name: f"/usr/bin/{name}" if name != "cmake" else None
        mock_sdks.return_value = [MagicMock(), MagicMock()]
        mock_list_devices.return_value = [MagicMock()]

        rep = run_checks()

        assert rep.platform == "linux"
        assert rep.arch == "x86_64"
        assert rep.sdk_count == 2
        assert rep.device_count == 1

        # Check that clang check is present and available
        clang_check = next((c for c in rep.checks if c.name == "clang"), None)
        assert clang_check is not None
        assert clang_check.available is True
        assert clang_check.required is True

        # Check that cmake is present but not available
        cmake_check = next((c for c in rep.checks if c.name == "cmake"), None)
        assert cmake_check is not None
        assert cmake_check.available is False
        assert cmake_check.required is False

    @patch("smartapple.doctor.get_platform", return_value="linux")
    @patch("platform.machine", return_value="x86_64")
    @patch("smartapple.doctor.check_tool", return_value=None)
    @patch("smartapple.doctor.list_installed_sdks", return_value=[])
    def test_run_checks_device_exception(
        self, mock_sdks, mock_check_tool, mock_machine, mock_platform
    ):
        with patch("smartapple.device.list_devices", side_effect=Exception("device error")):
            rep = run_checks()
            assert rep.device_count == 0


class TestPrintReport:
    @patch("smartapple.ui.banner")
    @patch("smartapple.ui.info")
    @patch("smartapple.ui.success")
    @patch("smartapple.ui.error")
    @patch("smartapple.ui.warning")
    @patch("smartapple.ui.summary")
    @patch("smartapple.ui.hint")
    @patch("smartapple.doctor._version_of", return_value="1.0.0")
    def test_print_report(
        self, mock_ver, mock_hint, mock_sum, mock_warn, mock_err, mock_succ, mock_info, mock_banner
    ):
        c1 = CheckResult("clang", "toolchain", available=True, path="/usr/bin/clang", required=True)
        c2 = CheckResult("make", "toolchain", available=False, required=True, install_hint="apt install make")
        c3 = CheckResult("cmake", "toolchain", available=False, required=False, install_hint="apt install cmake")

        rep = DoctorReport(platform="linux", arch="x86_64", checks=[c1, c2, c3], sdk_count=1, device_count=0)

        print_report(rep)

        mock_banner.assert_called_once_with("smart-apple-dev doctor")
        mock_succ.assert_called()
        mock_err.assert_called()
        mock_warn.assert_called()
        mock_sum.assert_called_once()


class TestInstallers:
    @patch("subprocess.run")
    @patch("os.chmod")
    def test_download_to_success(self, mock_chmod, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)
        dest = tmp_path / "downloaded.tar.xz"
        res = _download_to("http://example.com/file", dest)
        assert res is True
        mock_chmod.assert_called_once_with(dest, 0o755)

    @patch("subprocess.run")
    def test_download_to_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="404 Not Found")
        dest = tmp_path / "downloaded.tar.xz"
        res = _download_to("http://example.com/file", dest)
        assert res is False

    @patch("platform.machine", return_value="invalid_arch")
    def test_install_xtool_invalid_arch(self, mock_arch):
        assert install_xtool() is False

    @patch("platform.machine", return_value="x86_64")
    @patch("smartapple.doctor.get_tool_dir")
    @patch("smartapple.doctor._download_to", return_value=True)
    @patch("tarfile.open")
    def test_install_xtool_success(self, mock_tar, mock_dl, mock_get_dir, mock_arch, tmp_path):
        mock_get_dir.return_value = tmp_path
        tarball = tmp_path / "xtool-1.17.tar.xz"
        tarball.touch()
        binary = tmp_path / "xtool"
        binary.touch()

        mock_tar_ctx = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tar_ctx

        # Mock rglob to find executable binary
        with patch.object(Path, "rglob", return_value=[binary]):
            with patch("os.access", return_value=True):
                res = install_xtool()
                assert res is True

    def test_install_ldid_and_cctools(self, capsys):
        assert install_ldid() is False
        assert install_cctools() is False

    @patch("os.path.exists")
    def test_is_apt_system(self, mock_exists):
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt-get"
        assert _is_apt_system() is True

    @patch("smartapple.doctor._is_apt_system", return_value=False)
    def test_install_apt_pkgs_not_apt(self, mock_is_apt):
        assert install_apt_pkgs(["clang"]) is False

    @patch("smartapple.doctor._is_apt_system", return_value=True)
    @patch("subprocess.run")
    def test_install_apt_pkgs_success(self, mock_run, mock_is_apt):
        mock_run.return_value = MagicMock(returncode=0)
        assert install_apt_pkgs(["clang"]) is True
        assert install_clang_via_apt() is True
        assert install_cmake_via_apt() is True
        assert install_lld_via_apt() is True
        assert install_libimobiledevice_via_apt() is True

    @patch("smartapple.doctor.check_tool", return_value=None)
    def test_install_godot_export_templates_no_godot(self, mock_check):
        assert install_godot_export_templates() is False

    @patch("smartapple.doctor.check_tool", return_value="/usr/bin/godot")
    @patch("subprocess.run")
    def test_install_godot_export_templates_invalid_version(self, mock_run, mock_check):
        mock_run.return_value = MagicMock(returncode=0, stdout="Godot custom version", stderr="")
        assert install_godot_export_templates() is False

    @patch("smartapple.doctor.ensure_dirs")
    def test_install_all(self, mock_dirs):
        fn1 = MagicMock(return_value=True)
        fn2 = MagicMock(return_value=False)
        c1 = CheckResult("t1", "toolchain", available=False, install_fn=fn1)
        c2 = CheckResult("t2", "toolchain", available=False, install_fn=fn2)
        c3 = CheckResult("t3", "toolchain", available=True, install_fn=fn1)

        report = DoctorReport("linux", "x86_64", checks=[c1, c2, c3])
        res = install_all(report)
        assert res == 1
        fn1.assert_called_once()
        fn2.assert_called_once()
