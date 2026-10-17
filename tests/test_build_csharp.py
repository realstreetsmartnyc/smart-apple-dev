"""Tests for the C# build backend (CSharpBackend)."""

from pathlib import Path
import pytest

from smartapple.build.csharp import CSharpBackend, create_csharp_backend
from smartapple.core.config import ProjectConfig


def test_create_csharp_backend():
    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = create_csharp_backend(cfg)
    assert isinstance(backend, CSharpBackend)
    assert backend.config == cfg


def test_get_runtime_identifier():
    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = CSharpBackend(cfg)

    assert backend._get_runtime_identifier("ios") == "ios-arm64"
    assert backend._get_runtime_identifier("ios-simulator") == "iossimulator-x64"
    assert backend._get_runtime_identifier("macos") == "osx-arm64"
    assert backend._get_runtime_identifier("android") == ""
    assert backend._get_runtime_identifier("unknown") == ""


def test_build_dotnet_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: None)
    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path)

    assert not result.success
    assert result.language == "csharp"
    assert any("dotnet not found" in err for err in result.errors)


def test_build_no_csproj_found(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: "/usr/bin/dotnet")
    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path)

    assert not result.success
    assert result.language == "csharp"
    assert any("No .csproj file found" in err for err in result.errors)


def test_build_dotnet_success(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: "/usr/bin/dotnet")

    # Create dummy .csproj file
    csproj = tmp_path / "TestApp.csproj"
    csproj.write_text("<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><OutputType>Exe</OutputType></PropertyGroup></Project>")

    # Create dummy output artifact
    bin_dir = tmp_path / "bin" / "Debug"
    bin_dir.mkdir(parents=True)
    artifact_file = bin_dir / "TestApp.dll"
    artifact_file.write_text("dummy dll binary")

    recorded_cmds = []

    def mock_run_cmd(cmd, cwd, timeout):
        recorded_cmds.append((cmd, cwd, timeout))
        return (0, "Build succeeded.", "")

    monkeypatch.setattr("smartapple.build.csharp.run_cmd", mock_run_cmd)

    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path, target="ios", release=False)

    assert result.success
    assert result.language == "csharp"
    assert result.output == "Build succeeded."
    assert result.artifact == artifact_file
    assert result.errors == []
    assert result.metadata == {"framework": "dotnet", "target": "ios"}

    assert len(recorded_cmds) == 1
    cmd, cwd, timeout = recorded_cmds[0]
    assert cmd == ["/usr/bin/dotnet", "build", str(csproj), "-r", "ios-arm64"]
    assert cwd == tmp_path
    assert timeout == 600


def test_build_dotnet_release_and_target_args(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: "/usr/bin/dotnet")

    csproj = tmp_path / "TestApp.csproj"
    csproj.write_text("<Project Sdk=\"Microsoft.NET.Sdk\"></Project>")

    recorded_cmds = []

    def mock_run_cmd(cmd, cwd, timeout):
        recorded_cmds.append((cmd, cwd, timeout))
        return (0, "Release build done.", "")

    monkeypatch.setattr("smartapple.build.csharp.run_cmd", mock_run_cmd)

    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path, target="macos", release=True)

    assert result.success
    assert result.metadata == {"framework": "dotnet", "target": "macos"}

    assert len(recorded_cmds) == 1
    cmd, _, _ = recorded_cmds[0]
    assert cmd == ["/usr/bin/dotnet", "build", str(csproj), "--configuration", "Release", "-r", "osx-arm64"]


def test_build_dotnet_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: "/usr/bin/dotnet")

    csproj = tmp_path / "TestApp.csproj"
    csproj.write_text("<Project Sdk=\"Microsoft.NET.Sdk\"></Project>")

    def mock_run_cmd(cmd, cwd, timeout):
        return (1, "Compilation error output", "Build failed with exit code 1")

    monkeypatch.setattr("smartapple.build.csharp.run_cmd", mock_run_cmd)

    cfg = ProjectConfig(name="TestApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path, target="ios")

    assert not result.success
    assert result.language == "csharp"
    assert result.errors == ["Build failed with exit code 1"]
    assert result.metadata == {"framework": "dotnet", "target": "ios"}


def test_build_maui_fallback_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: "/usr/bin/dotnet")

    csproj = tmp_path / "MauiApp.csproj"
    csproj.write_text("<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><UseMaui>true</UseMaui></PropertyGroup></Project>")

    recorded_cmds = []

    def mock_run_cmd(cmd, cwd, timeout):
        recorded_cmds.append((cmd, cwd, timeout))
        if len(recorded_cmds) == 1:
            # First attempt: standard dotnet build fails
            return (1, "dotnet build failed for MAUI project", "Standard build not supported for MAUI")
        else:
            # Second attempt: dotnet maui build succeeds
            return (0, "dotnet maui build succeeded", "")

    monkeypatch.setattr("smartapple.build.csharp.run_cmd", mock_run_cmd)

    cfg = ProjectConfig(name="MauiApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path, target="ios", release=False)

    assert result.success
    assert result.language == "csharp"
    assert result.output == "dotnet maui build succeeded"
    assert result.errors == []
    assert result.metadata == {"framework": "maui", "target": "ios"}

    assert len(recorded_cmds) == 2
    cmd1, cwd1, timeout1 = recorded_cmds[0]
    assert cmd1[:3] == ["/usr/bin/dotnet", "build", str(csproj)]
    assert timeout1 == 600

    cmd2, cwd2, timeout2 = recorded_cmds[1]
    assert cmd2 == ["/usr/bin/dotnet", "maui", "build", "--target", "ios"]
    assert cwd2 == tmp_path
    assert timeout2 == 1200


def test_build_maui_release(tmp_path, monkeypatch):
    monkeypatch.setattr("smartapple.build.csharp.check_tool", lambda tool: "/usr/bin/dotnet")

    csproj = tmp_path / "MauiApp.csproj"
    csproj.write_text("<Project Sdk=\"Microsoft.NET.Sdk\"><UseMaui>true</UseMaui></Project>")

    recorded_cmds = []

    def mock_run_cmd(cmd, cwd, timeout):
        recorded_cmds.append((cmd, cwd, timeout))
        if len(recorded_cmds) == 1:
            return (1, "", "Standard build failed")
        return (0, "MAUI release succeeded", "")

    monkeypatch.setattr("smartapple.build.csharp.run_cmd", mock_run_cmd)

    cfg = ProjectConfig(name="MauiApp", language="csharp")
    backend = CSharpBackend(cfg)

    result = backend.build(cfg, tmp_path, target="macos", release=True)

    assert result.success
    assert result.metadata == {"framework": "maui", "target": "macos"}

    assert len(recorded_cmds) == 2
    cmd2, _, _ = recorded_cmds[1]
    assert cmd2 == ["/usr/bin/dotnet", "maui", "build", "--target", "macos", "--configuration=Release"]


def test_find_dotnet_artifact(tmp_path):
    cfg = ProjectConfig(name="MyApp", language="csharp")
    backend = CSharpBackend(cfg)
    csproj = tmp_path / "MyApp.csproj"

    assert backend._find_dotnet_artifact(tmp_path, csproj, "MyApp", "ios") is None

    # Test finding .dll
    bin_dll = tmp_path / "bin" / "MyApp.dll"
    bin_dll.parent.mkdir(parents=True)
    bin_dll.write_text("dll")
    assert backend._find_dotnet_artifact(tmp_path, csproj, "MyApp", "ios") == bin_dll

    # Test finding .app (takes precedence if searched, or found first)
    app_dir = tmp_path / "bin" / "MyApp.app"
    app_dir.mkdir(parents=True)
    # The helper iterates patterns ["MyApp.dll", "MyApp.app", "MyApp.ipa"]
    # So MyApp.dll will still match if it exists. Let's remove dll.
    bin_dll.unlink()
    assert backend._find_dotnet_artifact(tmp_path, csproj, "MyApp", "ios") == app_dir

    # Test finding .ipa
    app_dir.rmdir()
    ipa_file = tmp_path / "bin" / "MyApp.ipa"
    ipa_file.write_text("ipa")
    assert backend._find_dotnet_artifact(tmp_path, csproj, "MyApp", "ios") == ipa_file
