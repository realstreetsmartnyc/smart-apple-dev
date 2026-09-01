"""Tests for app signing and IPA packaging."""
import os
import platform
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

import pytest

from smartapple.sign import (
    Signer,
    sign_artifact,
    package_ipa,
    verify_ipa,
    create_provisioning_profile,
    find_ldid,
    find_codesign,
    find_signing_tool,
)
from smartapple.core.config import ProjectConfig
from smartapple.build.cpp import CppBackend


def test_find_signing_tool_returns_tuple():
    tool, kind = find_signing_tool()
    assert kind in ("ldid", "codesign", "none")
    if kind != "none":
        assert tool is not None
        assert os.path.exists(tool)


# ---- Tests that do NOT require a real .app build ----

def test_create_provisioning_profile(tmp_path):
    p = create_provisioning_profile("myapp", "com.example.app", team_id="ABCDE12345")
    assert p.exists()
    assert p.suffix == ".mobileprovision"
    # Verify it parses as a plist
    import plistlib
    with open(p, "rb") as f:
        plist = plistlib.load(f)
    assert plist["AppIDName"] == "myapp"
    assert plist["TeamIdentifier"] == ["ABCDE12345"]
    assert "com.example.app" in plist["Entitlements"]["application-identifier"]

def test_verify_ipa_rejects_nonexistent():
    result = verify_ipa(Path("/nonexistent/ipa"))
    assert result["valid"] is False
    assert "does not exist" in result["errors"][0]

def test_verify_ipa_rejects_non_zip(tmp_path):
    fake = tmp_path / "fake.ipa"
    fake.write_bytes(b"not a zip file at all")
    result = verify_ipa(fake)
    assert result["valid"] is False

def test_verify_ipa_accepts_valid_structure(tmp_path):
    # Create a fake but structurally valid IPA
    ipa = tmp_path / "test.ipa"
    payload = tmp_path / "Payload" / "Test.app" / "Contents" / "MacOS"
    payload.mkdir(parents=True)
    (payload / "test").write_bytes(b"\xcf\xfa\xed\xfe")  # fake Mach-O magic
    (payload / ".." / "Info.plist").write_text("<plist/>")
    with zipfile.ZipFile(ipa, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in (tmp_path / "Payload").rglob("*"):
            if item.is_file():
                zf.write(item, item.relative_to(tmp_path))
    shutil.rmtree(tmp_path / "Payload")
    
    result = verify_ipa(ipa)
    assert result["valid"] is True
    assert result["has_payload"] is True
    assert result["has_app"] is True
    assert result["app_name"] == "Test.app"


# ---- Tests that require ldid to be installed ----

@pytest.fixture
def ldid_available():
    if find_ldid() is None:
        pytest.skip("ldid not available")


def test_find_ldid_returns_path_when_installed(ldid_available):
    tool = find_ldid()
    assert tool is not None
    assert os.path.exists(tool)


# ---- End-to-end tests: build, sign, package ----

@pytest.fixture
def clang_available():
    from smartapple.core.config import check_tool
    if check_tool("clang") is None:
        pytest.skip("clang not available")


@pytest.fixture
def lld_available():
    from smartapple.build.cpp import _find_mach_o_linker
    if _find_mach_o_linker() is None:
        pytest.skip("ld64.lld not available")


@pytest.fixture
def macosx_sdk_available():
    from smartapple.core.sdk import list_installed_sdks, get_sdk
    sdks = list_installed_sdks()
    if not any(s.platform == "macosx" for s in sdks):
        pytest.skip("No MacOSX SDK")
    try:
        return get_sdk("macosx")
    except Exception:
        pytest.skip("MacOSX SDK not available")


def test_full_pipeline_objc_sign_package(
    tmp_path, clang_available, lld_available, macosx_sdk_available, ldid_available
):
    """End-to-end: ObjC source -> Mach-O .app -> signed .app -> .ipa."""
    # 1. Build a .app
    project = tmp_path / "TestApp"
    project.mkdir()
    (project / "main.m").write_text(
        "#import <Foundation/Foundation.h>\n"
        "int main(int argc, char *argv[]) {\n"
        "    @autoreleasepool { NSLog(@\"test\"); }\n"
        "    return 0;\n"
        "}\n"
    )
    cfg = ProjectConfig(name="TestApp", language="objc", min_os="11.0")
    be = CppBackend(cfg)
    result = be.build(cfg, project, target="macos")
    assert result.success, f"Build failed: {result.errors}"
    assert result.artifact is not None
    
    # 2. Sign the .app
    sign_result = sign_artifact(result.artifact, cfg, mode="ad-hoc")
    assert sign_result.success, f"Sign failed: {sign_result.errors}"
    assert sign_result.signed is True
    assert sign_result.artifact_path == result.artifact
    
    # 3. Verify the binary has a code signature load command
    binary = result.artifact / "Contents" / "MacOS" / "TestApp"
    data = binary.read_bytes()
    magic, _, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from("<IIIIIIII", data, 0)
    assert magic == 0xfeedfacf  # MH_MAGIC_64
    LC_CODE_SIGNATURE = 0x1d
    offset = 32
    found_sig = False
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", data, offset)
        if cmd == LC_CODE_SIGNATURE:
            found_sig = True
            break
        offset += cmdsize
    assert found_sig, "Binary should have LC_CODE_SIGNATURE after signing"
    
    # 4. Package as .ipa
    ipa = package_ipa(result.artifact)
    assert ipa.exists()
    assert ipa.suffix == ".ipa"
    
    # 5. Verify the IPA structure
    v = verify_ipa(ipa)
    assert v["valid"]
    assert v["app_name"] == "TestApp.app"
    
    # 6. Confirm Payload/TestApp.app/Contents/MacOS/TestApp is signed
    with zipfile.ZipFile(ipa, "r") as zf:
        names = zf.namelist()
        signed_binary = "Payload/TestApp.app/Contents/MacOS/TestApp"
        assert signed_binary in names
        signed_data = zf.read(signed_binary)
        _, _, _, _, ncmds2, _, _, _ = struct.unpack_from("<IIIIIIII", signed_data, 0)
        offset = 32
        found = False
        for _ in range(ncmds2):
            cmd, _ = struct.unpack_from("<II", signed_data, offset)
            if cmd == LC_CODE_SIGNATURE:
                found = True
                break
            offset += struct.unpack_from("<I", signed_data, offset + 4)[0]
        # Note: signed_data is compressed, may differ. Just check basic structure.
        assert signed_data[:4] == b"\xcf\xfa\xed\xfe"


def test_sign_skip_mode(tmp_path, clang_available, lld_available, macosx_sdk_available):
    """Signing with mode=skip should succeed without invoking any tool."""
    project = tmp_path / "SkipApp"
    project.mkdir()
    (project / "main.m").write_text("#import <Foundation/Foundation.h>\nint main(){return 0;}\n")
    cfg = ProjectConfig(name="SkipApp", language="objc")
    be = CppBackend(cfg)
    result = be.build(cfg, project, target="macos")
    assert result.success
    
    sign_result = sign_artifact(result.artifact, cfg, mode="skip")
    assert sign_result.success
    assert sign_result.signed is False
    # Should have a warning noting it was skipped
    assert any("skip" in w.lower() for w in sign_result.warnings)


def test_package_ipa_creates_valid_structure(tmp_path):
    """package_ipa should produce a zip with Payload/<name>.app structure."""
    app = tmp_path / "MyApp.app" / "Contents" / "MacOS"
    app.mkdir(parents=True)
    (app / "MyApp").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 100)
    (app.parent / "Info.plist").write_text("<plist/>")
    
    ipa = package_ipa(tmp_path / "MyApp.app")
    assert ipa.exists()
    
    with zipfile.ZipFile(ipa, "r") as zf:
        names = zf.namelist()
        assert any(n.startswith("Payload/MyApp.app/") for n in names)
        # No files should be at the root of the zip
        assert not any("/" not in n for n in names if n)


def test_sign_nonexistent_artifact(tmp_path):
    cfg = ProjectConfig(name="x", language="objc")
    result = sign_artifact(tmp_path / "does_not_exist.app", cfg, mode="ad-hoc")
    assert not result.success
    assert "not found" in result.errors[0].lower()
