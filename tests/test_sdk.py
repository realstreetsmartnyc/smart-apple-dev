"""Tests for smartapple.core.sdk."""
import json
from pathlib import Path

import pytest

from smartapple.core.sdk import (
    SdkError,
    SdkInfo,
    SDK_VERSIONS,
    list_available_sdks,
    list_installed_sdks,
    get_sdk,
    install_sdk,
)


def test_sdk_error_is_exception():
    assert issubclass(SdkError, Exception)


def test_sdk_info_round_trip():
    s = SdkInfo(version="18.0", platform="iphoneos", path=Path("/tmp/sdk"))
    d = s.to_dict()
    assert d["version"] == "18.0"
    assert d["platform"] == "iphoneos"
    s2 = SdkInfo.from_dict(d)
    assert s2.version == s.version
    assert s2.platform == s.platform


def test_sdk_versions_have_iphoneos():
    assert "iphoneos" in SDK_VERSIONS
    assert len(SDK_VERSIONS["iphoneos"]) >= 1


def test_sdk_versions_have_macosx():
    assert "macosx" in SDK_VERSIONS
    assert len(SDK_VERSIONS["macosx"]) >= 1


def test_list_available_sdks():
    available = list_available_sdks()
    assert len(available) >= 2
    for entry in available:
        assert "platform" in entry
        assert "version" in entry
        assert "url" in entry
        assert entry["url"].startswith("https://")


def test_list_installed_sdks_empty_when_no_index(tmp_path, monkeypatch):
    # Redirect SDK dir to a fresh tmp
    monkeypatch.setattr("smartapple.core.sdk.get_sdk_dir", lambda: tmp_path)
    assert list_installed_sdks() == []


def test_get_sdk_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.core.sdk.get_sdk_dir", lambda: tmp_path)
    with pytest.raises(SdkError) as exc:
        get_sdk("iphoneos")
    assert "No SDK installed" in str(exc.value)


def test_get_sdk_finds_installed(tmp_path, monkeypatch):
    # Create a fake installed SDK
    sdk_dir = tmp_path
    sdk_path = sdk_dir / "iphoneos-18.0.sdk"
    sdk_path.mkdir()

    # Write index
    index = [
        {"version": "18.0", "platform": "iphoneos", "path": str(sdk_path), "sha256": ""}
    ]
    (sdk_dir / "index.json").write_text(json.dumps(index))

    monkeypatch.setattr("smartapple.core.sdk.get_sdk_dir", lambda: sdk_dir)
    found = get_sdk("iphoneos")
    assert found == sdk_path


def test_install_sdk_unknown_platform():
    with pytest.raises(SdkError) as exc:
        install_sdk("watchos", "10.0")
    assert "Unknown SDK platform" in str(exc.value)


def test_install_sdk_unknown_version():
    with pytest.raises(SdkError) as exc:
        install_sdk("iphoneos", "99.99")
    assert "Unknown SDK version" in str(exc.value)
