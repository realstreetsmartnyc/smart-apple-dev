"""Pluggable provider system for smart-apple-dev.

A provider is a backend that can execute the build/sign/install/upload pipeline.
The current MVP has only the LocalProvider, but the interface is designed so that
remote providers (SSH-to-Mac, GitHub Actions, AWS Mac) can drop in.

The BuildOrchestrator already handles language dispatch. The Provider handles
*where* the build runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.config import ProjectConfig, get_arch
from ..core.sdk import list_installed_sdks


@dataclass
class ProviderCapabilities:
    """What a provider can do."""
    build: bool = False
    sign: bool = False
    install: bool = False
    upload: bool = False
    languages: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    requires_internet: bool = False
    cost_per_build: float = 0.0  # in USD


@dataclass
class ProviderResult:
    """Result of a provider operation."""
    success: bool
    artifact: Path | None = None
    output: str = ""
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "artifact": str(self.artifact) if self.artifact else None,
            "output": self.output,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


class BuildProvider(ABC):
    """Abstract base class for all build providers."""

    name: str = "abstract"
    description: str = ""
    requires_setup: bool = False

    def __init__(self, config: ProjectConfig | None = None):
        self.config = config

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return what this provider can do."""
        ...

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Check if the provider is ready to use. Returns (available, reason)."""
        ...

    @abstractmethod
    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        """Build the project. Returns a ProviderResult with the artifact path."""
        ...

    def sign(self, artifact: Path, config: ProjectConfig,
             **kwargs) -> ProviderResult:
        """Sign the artifact. Default: delegate to local sign."""
        from ..sign import sign_artifact, SignResult
        sr: SignResult = sign_artifact(artifact, config, **kwargs)
        return ProviderResult(
            success=sr.success,
            artifact=sr.artifact_path,
            output=sr.output,
            errors=sr.errors,
            metadata={"signed": sr.signed, "warnings": sr.warnings},
        )

    def install(self, artifact: Path, config: ProjectConfig,
                device_udid: str | None = None) -> ProviderResult:
        """Install to a device. Default: local install via libimobiledevice."""
        from ..device import install_ipa
        if artifact.suffix != ".ipa":
            return ProviderResult(
                success=False,
                errors=[f"Cannot install non-IPA artifact: {artifact}"],
            )
        ok = install_ipa(artifact, device_udid)
        return ProviderResult(
            success=ok,
            artifact=artifact,
            errors=[] if ok else ["ideviceinstaller failed"],
        )

    def upload(self, artifact: Path, config: ProjectConfig, **kwargs) -> ProviderResult:
        """Upload to App Store Connect. Default: local upload."""
        from ..store import upload_to_app_store
        if artifact.suffix != ".ipa":
            return ProviderResult(
                success=False,
                errors=[f"Cannot upload non-IPA artifact: {artifact}"],
            )
        r = upload_to_app_store(artifact, config, **kwargs)
        return ProviderResult(
            success=r.success,
            output=r.output,
            errors=r.errors,
        )


# ============================================================
# LocalProvider — runs everything on this machine
# ============================================================

class LocalProvider(BuildProvider):
    """Runs the build/sign/install pipeline locally.

    This is the default provider. It uses the local toolchain (clang, lld, ldid)
    and the local SDK installation.
    """

    name = "local"
    description = "Run the pipeline on this machine (Linux, Windows, or macOS)"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=False,
            cost_per_build=0.0,
        )

    def is_available(self) -> tuple[bool, str]:
        from ..core.config import check_tool
        if check_tool("clang") is None:
            return False, "clang not found. Install: apt install clang"
        from ..build.cpp import _find_mach_o_linker
        if _find_mach_o_linker() is None:
            return False, "No Mach-O linker (ld64.lld or cctools). Install: apt install lld"
        return True, "Local toolchain available"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        from .orchestrator import BuildOrchestrator
        from ..build.cpp import CppBackend
        from ..build.swift import SwiftBackend
        from ..build.rust import RustBackend
        from ..build.go import GoBackend
        from ..build.kotlin import KotlinBackend
        from time import perf_counter

        start = perf_counter()
        orch = BuildOrchestrator(project_dir)
        result = orch.build(config, target=target, release=release)
        duration = perf_counter() - start

        return ProviderResult(
            success=result.success,
            artifact=result.artifact,
            output=result.output,
            errors=result.errors,
            duration_seconds=duration,
            metadata={"language": result.language},
        )


# ============================================================
# Registry
# ============================================================

class ProviderRegistry:
    """Registry of available providers."""

    def __init__(self):
        self._providers: dict[str, BuildProvider] = {}
        # Register the built-in providers
        self.register(LocalProvider())
        # Register SSH provider (optional dependency)
        try:
            from .ssh_provider import SSHProvider
            self.register(SSHProvider())
        except ImportError:
            pass  # paramiko not installed

    def register(self, provider: BuildProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> BuildProvider | None:
        return self._providers.get(name)

    def list_available(self) -> list[BuildProvider]:
        """Return only providers that are currently available."""
        return [p for p in self._providers.values() if p.is_available()[0]]

    def list_all(self) -> list[BuildProvider]:
        return list(self._providers.values())

    def get_default(self) -> BuildProvider:
        """Get the first available provider, or LocalProvider as fallback."""
        available = self.list_available()
        if available:
            return available[0]
        return self.get("local") or LocalProvider()


# Module-level singleton
_REGISTRY: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ProviderRegistry()
    return _REGISTRY


def get_provider(name: str | None = None) -> BuildProvider:
    """Get a provider by name, or the default if name is None."""
    reg = get_registry()
    if name:
        p = reg.get(name)
        if p is None:
            raise ValueError(f"Unknown provider: {name}. Available: {[p.name for p in reg.list_all()]}")
        return p
    return reg.get_default()
