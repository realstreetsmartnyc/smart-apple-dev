"""Tests for the Kotlin build backend (KotlinBackend)."""

import stat
from pathlib import Path
from unittest import mock

import pytest

from smartapple.build.kotlin import KotlinBackend
from smartapple.core.config import ProjectConfig


def test_kotlin_backend_init():
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)
    assert backend.config == config


def test_kotlin_backend_missing_gradlew(tmp_path: Path):
    """Building without a gradlew script returns a clean error result."""
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)
    result = backend.build(config, tmp_path, target="ios")
    assert result.success is False
    assert result.language == "kotlin"
    assert result.artifact is None
    assert any("gradlew not found" in err for err in result.errors)


def test_kotlin_backend_native_ios(tmp_path: Path):
    """Building target=ios generates gradlew binaries --target iosArm64."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="ios", release=False)

    assert result.success is True
    assert result.language == "kotlin"
    assert result.output == "BUILD SUCCESSFUL"
    assert result.errors == []
    mock_run.assert_called_once_with(
        ["./gradlew", "binaries", "--target", "iosArm64"],
        cwd=tmp_path,
        timeout=600,
    )


def test_kotlin_backend_native_ios_simulator(tmp_path: Path):
    """Building target=ios-simulator maps to kotlin target iosX64."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="ios-simulator")

    assert result.success is True
    mock_run.assert_called_once_with(
        ["./gradlew", "binaries", "--target", "iosX64"],
        cwd=tmp_path,
        timeout=600,
    )


def test_kotlin_backend_native_macos(tmp_path: Path):
    """Building target=macos maps to kotlin target macosArm64."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="macos")

    assert result.success is True
    mock_run.assert_called_once_with(
        ["./gradlew", "binaries", "--target", "macosArm64"],
        cwd=tmp_path,
        timeout=600,
    )


def test_kotlin_backend_native_unknown_target_fallback(tmp_path: Path):
    """Unknown target falls back to iosArm64."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="unknown-target")

    assert result.success is True
    mock_run.assert_called_once_with(
        ["./gradlew", "binaries", "--target", "iosArm64"],
        cwd=tmp_path,
        timeout=600,
    )


def test_kotlin_backend_native_release(tmp_path: Path):
    """Release mode appends -P kotlin.binary.release=true."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="ios", release=True)

    assert result.success is True
    mock_run.assert_called_once_with(
        ["./gradlew", "binaries", "--target", "iosArm64", "-P", "kotlin.binary.release=true"],
        cwd=tmp_path,
        timeout=600,
    )


def test_kotlin_backend_native_artifact_kexe(tmp_path: Path):
    """Finds .kexe artifact matching config.name."""
    (tmp_path / "gradlew").touch()
    binaries_dir = tmp_path / "build" / "binaries"
    binaries_dir.mkdir(parents=True)
    kexe_file = binaries_dir / "MyApp.kexe"
    kexe_file.touch()

    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="ios")

    assert result.success is True
    assert result.artifact == kexe_file


def test_kotlin_backend_native_artifact_framework(tmp_path: Path):
    """Finds .framework artifact matching config.name if no .kexe exists."""
    (tmp_path / "gradlew").touch()
    binaries_dir = tmp_path / "build" / "binaries"
    binaries_dir.mkdir(parents=True)
    framework_dir = binaries_dir / "MyApp.framework"
    framework_dir.mkdir()

    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="ios")

    assert result.success is True
    assert result.artifact == framework_dir


def test_kotlin_backend_native_artifact_kexe_preferred(tmp_path: Path):
    """Prefers .kexe over .framework when both are present."""
    (tmp_path / "gradlew").touch()
    binaries_dir = tmp_path / "build" / "binaries"
    binaries_dir.mkdir(parents=True)
    framework_dir = binaries_dir / "MyApp.framework"
    framework_dir.mkdir()
    kexe_file = binaries_dir / "MyApp.kexe"
    kexe_file.touch()

    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (0, "BUILD SUCCESSFUL", "")
        result = backend.build(config, tmp_path, target="ios")

    assert result.success is True
    assert result.artifact == kexe_file


def test_kotlin_backend_native_failure(tmp_path: Path):
    """Failure exit code captures stderr as error."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (1, "BUILD FAILED", "e: Syntax error in file.kt")
        result = backend.build(config, tmp_path, target="ios")

    assert result.success is False
    assert result.artifact is None
    assert result.errors == ["e: Syntax error in file.kt"]


def test_kotlin_backend_native_failure_empty_stderr(tmp_path: Path):
    """Failure with empty stderr results in empty errors list."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch("smartapple.build.kotlin.run_cmd") as mock_run:
        mock_run.return_value = (1, "BUILD FAILED", "")
        result = backend.build(config, tmp_path, target="ios")

    assert result.success is False
    assert result.errors == []


def test_kotlin_backend_android_target_routing(tmp_path: Path):
    """Target='android' routes to _build_android."""
    (tmp_path / "gradlew").touch()
    config = ProjectConfig(name="MyApp", language="kotlin")
    backend = KotlinBackend(config)

    with mock.patch.object(backend, "_build_android") as mock_android:
        expected_res = mock.MagicMock()
        mock_android.return_value = expected_res
        res = backend.build(config, tmp_path, target="android", release=True)

    assert res == expected_res
    mock_android.assert_called_once_with(config, tmp_path, True)
