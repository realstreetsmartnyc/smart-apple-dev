"""Tests for SwiftBackend build module (smartapple/build/swift.py)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from smartapple.build.swift import SwiftBackend
from smartapple.core.config import ProjectConfig


@pytest.fixture
def sample_config():
    return ProjectConfig(name="MyApp", language="swift")


def test_is_available_when_xtool_present(sample_config):
    with patch("smartapple.build.swift.check_tool", return_value="/usr/local/bin/xtool"):
        backend = SwiftBackend(sample_config)
        assert backend.is_available() is True


def test_is_available_when_xtool_missing(sample_config):
    with patch("smartapple.build.swift.check_tool", return_value=None):
        backend = SwiftBackend(sample_config)
        assert backend.is_available() is False


def test_target_triple_mapping(sample_config):
    backend = SwiftBackend(sample_config)
    assert backend._target_triple("ios") == "ios"
    assert backend._target_triple("ios-simulator") == "ios-simulator"
    assert backend._target_triple("macos") == "macos"
    assert backend._target_triple("catalyst") == "catalyst"
    assert backend._target_triple("watchos") == "watchos"
    assert backend._target_triple("tvos") == "tvos"
    assert backend._target_triple("unknown-target") == "ios"


def test_build_xtool_not_found(sample_config, tmp_path):
    with patch("smartapple.build.swift.check_tool", return_value=None):
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path)

        assert result.success is False
        assert result.language == "swift"
        assert result.artifact is None
        assert len(result.errors) == 1
        assert "xtool not found" in result.errors[0]


def test_build_debug_default_target(sample_config, tmp_path):
    with patch("smartapple.build.swift.check_tool", return_value="/usr/bin/xtool"), \
         patch("smartapple.build.swift.run_cmd", return_value=(0, "Build succeeded", "")) as mock_run_cmd:
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path)

        mock_run_cmd.assert_called_once_with(
            ["/usr/bin/xtool", "build", "--target", "ios"],
            cwd=tmp_path,
        )
        assert result.success is True
        assert result.output == "Build succeeded"
        assert result.errors == []
        assert result.language == "swift"
        assert result.artifact is None


def test_build_release_custom_target(sample_config, tmp_path):
    with patch("smartapple.build.swift.check_tool", return_value="/usr/bin/xtool"), \
         patch("smartapple.build.swift.run_cmd", return_value=(0, "Build succeeded", "")) as mock_run_cmd:
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path, target="macos", release=True)

        mock_run_cmd.assert_called_once_with(
            ["/usr/bin/xtool", "build", "-c", "release", "--target", "macos"],
            cwd=tmp_path,
        )
        assert result.success is True


def test_build_failure_returns_errors(sample_config, tmp_path):
    stderr_msg = "Error: compilation failed"
    with patch("smartapple.build.swift.check_tool", return_value="/usr/bin/xtool"), \
         patch("smartapple.build.swift.run_cmd", return_value=(1, "", stderr_msg)):
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path)

        assert result.success is False
        assert result.errors == [stderr_msg]


def test_build_finds_ipa_artifact(sample_config, tmp_path):
    build_dir = tmp_path / ".build"
    build_dir.mkdir()
    ipa_file = build_dir / "MyApp.ipa"
    ipa_file.touch()

    with patch("smartapple.build.swift.check_tool", return_value="/usr/bin/xtool"), \
         patch("smartapple.build.swift.run_cmd", return_value=(0, "Build OK", "")):
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path)

        assert result.success is True
        assert result.artifact == ipa_file


def test_build_finds_app_artifact_when_no_ipa(sample_config, tmp_path):
    build_dir = tmp_path / ".build"
    build_dir.mkdir()
    app_dir = build_dir / "MyApp.app"
    app_dir.mkdir()

    with patch("smartapple.build.swift.check_tool", return_value="/usr/bin/xtool"), \
         patch("smartapple.build.swift.run_cmd", return_value=(0, "Build OK", "")):
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path)

        assert result.success is True
        assert result.artifact == app_dir


def test_build_prefers_ipa_over_app_artifact(sample_config, tmp_path):
    build_dir = tmp_path / ".build"
    build_dir.mkdir()
    app_dir = build_dir / "MyApp.app"
    app_dir.mkdir()
    ipa_file = build_dir / "MyApp.ipa"
    ipa_file.touch()

    with patch("smartapple.build.swift.check_tool", return_value="/usr/bin/xtool"), \
         patch("smartapple.build.swift.run_cmd", return_value=(0, "Build OK", "")):
        backend = SwiftBackend(sample_config)
        result = backend.build(sample_config, tmp_path)

        assert result.success is True
        assert result.artifact == ipa_file
