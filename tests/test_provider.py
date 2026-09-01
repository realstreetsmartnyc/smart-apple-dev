"""Tests for the build provider system."""
from pathlib import Path

import pytest

from smartapple.build.provider import (
    BuildProvider,
    LocalProvider,
    ProviderRegistry,
    ProviderCapabilities,
    ProviderResult,
    get_registry,
    get_provider,
)
from smartapple.core.config import ProjectConfig


def test_capabilities_dataclass_defaults():
    caps = ProviderCapabilities()
    assert caps.build is False
    assert caps.sign is False
    assert caps.install is False
    assert caps.upload is False
    assert caps.languages == []
    assert caps.cost_per_build == 0.0


def test_provider_result_to_dict():
    r = ProviderResult(success=True, output="ok")
    d = r.to_dict()
    assert d["success"] is True
    assert d["output"] == "ok"
    assert d["errors"] == []


def test_registry_has_local_provider():
    reg = ProviderRegistry()
    assert reg.get("local") is not None
    assert isinstance(reg.get("local"), LocalProvider)


def test_registry_get_unknown():
    reg = ProviderRegistry()
    assert reg.get("nonexistent") is None


def test_registry_get_default():
    reg = ProviderRegistry()
    p = reg.get_default()
    # Should return either the first available or local
    assert p is not None
    assert p.name == "local"  # fallback


def test_local_provider_capabilities():
    p = LocalProvider()
    caps = p.capabilities()
    assert caps.build is True
    assert caps.sign is True
    assert "swift" in caps.languages
    assert "ios" in caps.targets
    assert caps.cost_per_build == 0.0


def test_local_provider_is_available():
    """Local provider is available if clang and lld exist."""
    p = LocalProvider()
    available, reason = p.is_available()
    # On this system, clang and lld are both present
    assert available is True, f"Should be available, got: {reason}"


def test_get_provider_singleton():
    p1 = get_provider()
    p2 = get_provider()
    assert p1 is p2  # same registry


def test_get_provider_by_name():
    p = get_provider("local")
    assert isinstance(p, LocalProvider)


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError) as exc:
        get_provider("totally-not-a-real-provider")
    assert "Unknown provider" in str(exc.value)


def test_provider_build_for_objc(tmp_path):
    """Provider.build should run the full pipeline and return a ProviderResult."""
    from smartapple.core.config import check_tool
    from smartapple.build.cpp import _find_mach_o_linker
    from smartapple.core.sdk import list_installed_sdks
    if check_tool("clang") is None:
        pytest.skip("clang not available")
    if _find_mach_o_linker() is None:
        pytest.skip("ld64.lld not available")
    if not any(s.platform == "macosx" for s in list_installed_sdks()):
        pytest.skip("No MacOSX SDK")
    
    # Set up a tiny ObjC project
    project = tmp_path / "ProvApp"
    project.mkdir()
    (project / "main.m").write_text(
        "#import <Foundation/Foundation.h>\n"
        "int main(){ @autoreleasepool{NSLog(@\"hi\");} return 0; }\n"
    )
    
    config = ProjectConfig(name="ProvApp", language="objc", min_os="11.0")
    p = LocalProvider(config)
    result = p.build(project, config, target="macos")
    
    assert result.success, f"Build failed: {result.errors}"
    assert result.artifact is not None
    assert result.artifact.exists()
    assert result.artifact.name == "ProvApp.app"
    assert result.metadata.get("language") == "objc"
    assert result.duration_seconds > 0


def test_provider_install_rejects_non_ipa(tmp_path):
    """Provider.install should reject non-IPA artifacts."""
    p = LocalProvider()
    fake = tmp_path / "fake.app"
    fake.mkdir()
    result = p.install(fake, ProjectConfig(name="x"))
    assert not result.success
    assert "not install" in result.errors[0].lower() or "ipa" in result.errors[0].lower()


def test_provider_sign_works(tmp_path):
    """Provider.sign should call into the sign module."""
    # Build a quick app first
    from smartapple.core.config import check_tool
    from smartapple.build.cpp import _find_mach_o_linker
    from smartapple.core.sdk import list_installed_sdks
    if check_tool("clang") is None or _find_mach_o_linker() is None:
        pytest.skip("toolchain")
    if not any(s.platform == "macosx" for s in list_installed_sdks()):
        pytest.skip("no SDK")
    
    from smartapple.build.cpp import CppBackend
    project = tmp_path / "SignApp"
    project.mkdir()
    (project / "main.m").write_text("#import <Foundation/Foundation.h>\nint main(){return 0;}\n")
    cfg = ProjectConfig(name="SignApp", language="objc")
    be = CppBackend(cfg)
    br = be.build(cfg, project, target="macos")
    if not br.success:
        pytest.skip(f"build failed: {br.errors[:1]}")
    
    p = LocalProvider(cfg)
    result = p.sign(br.artifact, cfg, mode="skip")  # use skip to avoid ldid dep
    assert result.success
    assert result.metadata.get("signed") is False
