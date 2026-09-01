"""Tests for the C/C++/ObjC build pipeline (CppBackend)."""
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from smartapple.build.cpp import (
    CppBackend,
    _find_mach_o_linker,
    _mach_o_arch_for_target,
    _mach_o_target_for,
    _is_c_source,
    _is_cpp_source,
    _is_objc_source,
    _is_swift_source,
)
from smartapple.core.config import check_tool, get_arch, get_sdk_dir
from smartapple.core.sdk import get_sdk, list_installed_sdks
from smartapple.core.config import ProjectConfig


# Pure-function tests

def test_is_c_source():
    assert _is_c_source(Path("foo.c"))
    assert not _is_c_source(Path("foo.cpp"))
    assert not _is_c_source(Path("foo.m"))

def test_is_cpp_source():
    assert _is_cpp_source(Path("foo.cpp"))
    assert _is_cpp_source(Path("foo.cc"))
    assert _is_cpp_source(Path("foo.cxx"))
    assert not _is_cpp_source(Path("foo.c"))

def test_is_objc_source():
    assert _is_objc_source(Path("Foo.m"))
    assert _is_objc_source(Path("Foo.mm"))
    assert not _is_objc_source(Path("Foo.c"))

def test_is_swift_source():
    assert _is_swift_source(Path("Foo.swift"))
    assert not _is_swift_source(Path("Foo.m"))

def test_mach_o_target_for_macos():
    t = _mach_o_target_for("arm64", "macosx", "11.0")
    assert t == "arm64-apple-darwin11.0"

def test_mach_o_target_for_ios():
    t = _mach_o_target_for("arm64", "iphoneos", "15.0")
    assert t == "arm64-apple-ios15.0"

def test_mach_o_target_for_simulator():
    t = _mach_o_target_for("x86_64", "iphonesimulator", "16.0")
    assert t == "x86_64-apple-ios16.0-simulator"

def test_mach_o_arch_for_target_ios():
    arch = _mach_o_arch_for_target("ios", "x86_64")
    assert arch == "arm64"

def test_mach_o_arch_for_target_macos_arm_host():
    arch = _mach_o_arch_for_target("macos", "arm64")
    assert arch == "arm64"

def test_mach_o_arch_for_target_macos_x86_host():
    arch = _mach_o_arch_for_target("macos", "x86_64")
    assert arch == "x86_64"


# Integration tests (require toolchain)

@pytest.fixture
def clang_available():
    if check_tool("clang") is None:
        pytest.skip("clang not available")

@pytest.fixture
def lld_available():
    if _find_mach_o_linker() is None:
        pytest.skip("ld64.lld not available")

@pytest.fixture
def macosx_sdk_available():
    sdks = list_installed_sdks()
    if not any(s.platform == "macosx" for s in sdks):
        pytest.skip("No MacOSX SDK installed")
    try:
        p = get_sdk("macosx")
        if not p.exists():
            pytest.skip("MacOSX SDK path does not exist")
    except Exception:
        pytest.skip("MacOSX SDK not available")
    return p

def test_find_mach_o_linker_returns_something(lld_available):
    linker = _find_mach_o_linker()
    assert linker is not None
    assert os.path.exists(linker)

def test_cpp_backend_is_available_when_toolchain_present(clang_available, lld_available):
    cfg = ProjectConfig(name="x", language="cpp")
    be = CppBackend(cfg)
    assert be.is_available()

def test_cpp_backend_is_not_available_without_lld(clang_available):
    import smartapple.build.cpp as mod
    orig = mod._find_mach_o_linker
    mod._find_mach_o_linker = lambda: None
    try:
        cfg = ProjectConfig(name="x", language="cpp")
        be = CppBackend(cfg)
        assert not be.is_available()
    finally:
        mod._find_mach_o_linker = orig

def test_build_objc_to_macho(tmp_path, clang_available, lld_available, macosx_sdk_available):
    """Build an ObjC program into a real Mach-O .app on Linux."""
    project = tmp_path / "HelloApp"
    project.mkdir()
    objc_src = project / "main.m"
    objc_src.write_text("#import <Foundation/Foundation.h>\nint main(int argc, char *argv[]) {\n    @autoreleasepool { NSLog(@\"Hello!\"); }\n    return 0;\n}\n")
    cfg = ProjectConfig(name="HelloApp", language="objc", bundle_id="com.test.HelloApp", min_os="11.0")
    backend = CppBackend(cfg)
    result = backend.build(cfg, project, target="macos", release=False)
    assert result.success, f"Build failed: {result.errors}"
    assert result.artifact is not None
    assert result.artifact.exists()
    assert result.artifact.name == "HelloApp.app"
    binary = result.artifact / "Contents" / "MacOS" / "HelloApp"
    assert binary.exists()
    data = binary.read_bytes()
    assert data[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"), f"Not Mach-O 64-bit: {data[:4].hex()}"
    assert (result.artifact / "Contents" / "Info.plist").exists()
    assert (result.artifact / "Contents" / "PkgInfo").exists()

def test_build_cpp_with_libcxx(tmp_path, clang_available, lld_available, macosx_sdk_available):
    """Build C++ with std::cout; libc++ linked."""
    project = tmp_path / "CppTest"
    project.mkdir()
    (project / "main.cpp").write_text("#include <iostream>\nint main() { std::cout << \"ok\" << std::endl; return 0; }\n")
    cfg = ProjectConfig(name="CppTest", language="cpp", min_os="11.0")
    backend = CppBackend(cfg)
    result = backend.build(cfg, project, target="macos")
    assert result.success, f"Build failed: {result.errors[:1]}"

def test_build_no_sources_fails(tmp_path, clang_available, lld_available, macosx_sdk_available):
    """Building an empty project returns a clean error."""
    project = tmp_path / "Empty"
    project.mkdir()
    (project / "readme.txt").write_text("nothing")
    cfg = ProjectConfig(name="Empty", language="objc")
    backend = CppBackend(cfg)
    result = backend.build(cfg, project, target="macos")
    assert not result.success
    assert any("source" in e.lower() for e in result.errors)
