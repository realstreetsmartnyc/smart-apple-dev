"""Tests for C# build backend."""

from pathlib import Path
import pytest
from smartapple.build.csharp import CSharpBackend, create_csharp_backend
from smartapple.core.config import ProjectConfig


@pytest.fixture
def csharp_backend():
    config = ProjectConfig(name="MyApp", language="csharp")
    return CSharpBackend(config)


def test_create_csharp_backend():
    config = ProjectConfig(name="MyApp", language="csharp")
    backend = create_csharp_backend(config)
    assert isinstance(backend, CSharpBackend)


def test_find_dotnet_artifact_dll(csharp_backend, tmp_path):
    project_dir = tmp_path / "project"
    bin_dir = project_dir / "bin" / "Debug" / "net8.0-ios"
    bin_dir.mkdir(parents=True)

    dll_file = bin_dir / "MyApp.dll"
    dll_file.write_text("fake dll")

    csproj_path = project_dir / "MyApp.csproj"
    csproj_path.write_text("<Project></Project>")

    found = csharp_backend._find_dotnet_artifact(project_dir, csproj_path, "MyApp", "ios")
    assert found == dll_file


def test_find_dotnet_artifact_app_priority(csharp_backend, tmp_path):
    project_dir = tmp_path / "project"
    bin_dir = project_dir / "bin" / "Release"
    bin_dir.mkdir(parents=True)

    app_file = bin_dir / "MyApp.app"
    app_file.mkdir()
    ipa_file = bin_dir / "MyApp.ipa"
    ipa_file.write_text("fake ipa")

    csproj_path = project_dir / "MyApp.csproj"
    csproj_path.write_text("<Project></Project>")

    found = csharp_backend._find_dotnet_artifact(project_dir, csproj_path, "MyApp", "ios")
    # MyApp.app is higher priority than MyApp.ipa
    assert found == app_file


def test_find_dotnet_artifact_none(csharp_backend, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    csproj_path = project_dir / "MyApp.csproj"
    csproj_path.write_text("<Project></Project>")

    found = csharp_backend._find_dotnet_artifact(project_dir, csproj_path, "MyApp", "ios")
    assert found is None
