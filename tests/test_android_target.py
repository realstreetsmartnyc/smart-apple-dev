"""Tests for the Android build target and adb-based device install.

These tests cover the dispatch logic and the adb wrapper without requiring
a real Android SDK or a connected device — they mock out subprocess calls
or test pure data transforms.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest import mock

import pytest

from smartapple.build.kotlin import KotlinBackend
from smartapple.build.orchestrator import BuildOrchestrator
from smartapple.core.config import ProjectConfig
from smartapple.device import AndroidDevice, list_android_devices, install_apk


# ---------------------------------------------------------------------------
# Build dispatch
# ---------------------------------------------------------------------------

class TestAndroidTargetDispatch:
    def test_android_is_a_valid_target(self):
        """The orchestrator's Kotlin backend must accept 'android' as a target."""
        backend = KotlinBackend(ProjectConfig(name="hello"))
        # Just confirm the dispatch method exists; we don't actually run gradle.
        assert hasattr(backend, "build")
        assert hasattr(backend, "_build_android")
        assert hasattr(backend, "_build_native")

    def test_android_failure_diagnosis(self):
        """Common Android errors should produce actionable hints."""
        assert "ANDROID_HOME" in KotlinBackend._diagnose_android_failure(
            "SDK location not found. Define a valid SDK location with an ANDROID_SDK_ROOT "
            "environment variable or by setting the sdk.dir path in your project's local "
            "properties file at 'android/local.properties'."
        )
        assert "JDK 17" in KotlinBackend._diagnose_android_failure(
            "Could not find tools.jar. Please check that JDK 11 is installed."
        )
        assert "licenses" in KotlinBackend._diagnose_android_failure(
            "Failed to install the following Android SDK packages as some licences have not been accepted"
        ).lower()
        assert "chmod" in KotlinBackend._diagnose_android_failure(
            "Permission denied: ./gradlew"
        )
        # Unknown errors return empty hint
        assert KotlinBackend._diagnose_android_failure("something else went wrong") == ""


class TestBuildOrchestratorAndroidChecks:
    def test_kotlin_backend_checks_include_adb(self):
        orch = BuildOrchestrator()
        checks = orch._backend_checks("kotlin")
        assert "adb" in checks
        assert checks["adb"] == ["adb"]
        assert "gradle" in checks

    def test_check_backend_availability_kotlin(self):
        orch = BuildOrchestrator()
        info = orch.check_backend_availability("kotlin")
        assert info["backend"] == "kotlin"
        assert "gradle" in info["checks"]
        assert "adb" in info["checks"]


# ---------------------------------------------------------------------------
# Gradle integration (mocked)
# ---------------------------------------------------------------------------

class TestAndroidBuildMocked:
    def test_android_build_assembles_debug(self, tmp_path: Path):
        """assembleDebug is invoked; APK at the standard Gradle path is returned."""
        project = tmp_path / "hello"
        project.mkdir()
        # Fake gradlew + a Gradle project that doesn't actually need Java
        (project / "gradlew").write_text("#!/bin/sh\necho mocked\n")
        (project / "gradlew").chmod(stat.S_IRWXU)

        # Pretend gradle wrote an APK
        apk_dir = project / "build" / "outputs" / "apk" / "debug"
        apk_dir.mkdir(parents=True)
        apk = apk_dir / "hello-debug.apk"
        apk.write_bytes(b"fake apk content")

        config = ProjectConfig(name="hello", bundle_id="com.example.hello")

        with mock.patch("smartapple.build.kotlin.run_cmd") as rc:
            rc.return_value = (0, "BUILD SUCCESSFUL", "")
            backend = KotlinBackend(config)
            result = backend.build(config, project, target="android", release=False)

        assert result.success is True
        assert result.language == "kotlin"
        assert result.artifact == apk
        # assembleDebug was the gradle task
        args = rc.call_args[0][0]
        assert "assembleDebug" in args
        assert args[0].endswith("gradlew")

    def test_android_build_release(self, tmp_path: Path):
        project = tmp_path / "hello"
        project.mkdir()
        (project / "gradlew").write_text("#!/bin/sh\n")
        apk_dir = project / "build" / "outputs" / "apk" / "release"
        apk_dir.mkdir(parents=True)
        apk = apk_dir / "hello-release.apk"
        apk.write_bytes(b"fake")
        config = ProjectConfig(name="hello")

        with mock.patch("smartapple.build.kotlin.run_cmd") as rc:
            rc.return_value = (0, "OK", "")
            backend = KotlinBackend(config)
            result = backend.build(config, project, target="android", release=True)

        assert result.success is True
        assert "assembleRelease" in rc.call_args[0][0]
        assert result.artifact == apk

    def test_android_build_no_apk_is_failure(self, tmp_path: Path):
        project = tmp_path / "hello"
        project.mkdir()
        (project / "gradlew").write_text("#!/bin/sh\n")
        config = ProjectConfig(name="hello")
        with mock.patch("smartapple.build.kotlin.run_cmd") as rc:
            rc.return_value = (0, "OK", "")
            backend = KotlinBackend(config)
            result = backend.build(config, project, target="android")
        assert result.success is False
        assert result.artifact is None
        assert result.errors

    def test_android_build_sdk_missing_yields_hint(self, tmp_path: Path):
        project = tmp_path / "hello"
        project.mkdir()
        (project / "gradlew").write_text("#!/bin/sh\n")
        config = ProjectConfig(name="hello")
        with mock.patch("smartapple.build.kotlin.run_cmd") as rc:
            rc.return_value = (
                1,
                "",
                "SDK location not found. Define a valid SDK location with an ANDROID_SDK_ROOT",
            )
            backend = KotlinBackend(config)
            result = backend.build(config, project, target="android")
        assert any("ANDROID_HOME" in e for e in result.errors)


# ---------------------------------------------------------------------------
# adb device install
# ---------------------------------------------------------------------------

class TestAndroidDeviceList:
    def test_no_adb_returns_empty(self):
        with mock.patch("smartapple.device.check_tool", return_value=None):
            assert list_android_devices() == []

    def test_parses_adb_devices_l(self):
        adb_output = (
            "List of devices attached\n"
            "emulator-5554   device product:sdk_gphone64_x86_64 model:Android_SDK_built_for_x86_64 device:emulator64\n"
            "0123456789ABCDEF  unauthorized product:bramble model:Pixel_5\n"
        )
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd", return_value=(0, adb_output, "")):
            devices = list_android_devices()
        assert len(devices) == 2
        assert devices[0].serial == "emulator-5554"
        assert devices[0].state == "device"
        assert devices[0].product == "sdk_gphone64_x86_64"
        assert devices[0].model == "Android_SDK_built_for_x86_64"
        assert devices[0].transport == "tcp"
        assert devices[1].serial == "0123456789ABCDEF"
        assert devices[1].state == "unauthorized"
        assert devices[1].transport == "usb"

    def test_handles_no_devices(self):
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd", return_value=(0, "List of devices attached\n", "")):
            assert list_android_devices() == []


class TestAndroidDeviceInstall:
    def test_install_apk_missing_file(self, tmp_path: Path):
        assert install_apk(tmp_path / "nope.apk") is False

    def test_install_apk_no_adb(self, tmp_path: Path):
        apk = tmp_path / "hello.apk"
        apk.write_bytes(b"x")
        with mock.patch("smartapple.device.check_tool", return_value=None):
            assert install_apk(apk) is False

    def test_install_apk_no_devices(self, tmp_path: Path):
        apk = tmp_path / "hello.apk"
        apk.write_bytes(b"x")
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd", return_value=(0, "List of devices attached\n", "")):
            assert install_apk(apk) is False

    def test_install_apk_success(self, tmp_path: Path):
        apk = tmp_path / "hello.apk"
        apk.write_bytes(b"x")
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd") as rc:
            # First call: list devices. Second: install.
            rc.side_effect = [
                (0, "List of devices attached\nemulator-5554  device\n", ""),
                (0, "Success\n", ""),
            ]
            assert install_apk(apk) is True
        # Verify install was called with the right args
        install_call = rc.call_args_list[1]
        assert install_call[0][0] == [
            "/usr/bin/adb", "-s", "emulator-5554", "install", "-r", str(apk)
        ]

    def test_install_apk_specific_device(self, tmp_path: Path):
        apk = tmp_path / "hello.apk"
        apk.write_bytes(b"x")
        devices_out = "List of devices attached\ndev1  device\ndev2  device\n"
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd") as rc:
            rc.side_effect = [
                (0, devices_out, ""),
                (0, "Success\n", ""),
            ]
            assert install_apk(apk, device_serial="dev2") is True
        assert "-s" in rc.call_args_list[1][0][0]
        assert "dev2" in rc.call_args_list[1][0][0]

    def test_install_apk_unknown_serial(self, tmp_path: Path):
        apk = tmp_path / "hello.apk"
        apk.write_bytes(b"x")
        devices_out = "List of devices attached\ndev1  device\n"
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd", return_value=(0, devices_out, "")):
            assert install_apk(apk, device_serial="ghost") is False

    def test_install_failure_unauthorized(self, tmp_path: Path):
        apk = tmp_path / "hello.apk"
        apk.write_bytes(b"x")
        devices_out = "List of devices attached\ndev1  device\n"
        with mock.patch("smartapple.device.check_tool", return_value="/usr/bin/adb"), \
             mock.patch("smartapple.device.run_cmd") as rc:
            rc.side_effect = [
                (0, devices_out, ""),
                (1, "", "error: device unauthorized. Please accept the RSA prompt."),
            ]
            assert install_apk(apk) is False
