"""Pluggable provider system for smart-apple-dev.

A provider is a backend that can execute the build/sign/install/upload pipeline.
The system supports local builds, remote Mac builds via SSH, and cloud provider
CI/CD platforms (GitHub Actions, AWS Mac, Azure, CircleCI, MacStadium, Codemagic,
Bitrise, Jenkins, BuildJet, Nevercode).

The BuildOrchestrator handles language dispatch. The Provider handles *where* the build runs.
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

from ..core.config import ProjectConfig, get_arch, check_tool
from ..core.sdk import list_installed_sdks
from ..build.orchestrator import run_cmd


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
    platform: str = "any"  # any, macos, ios


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
    """Abstract base class for all build providers.

    Providers handle *where* the build runs (local machine, remote SSH, or cloud CI).
    Each provider must implement:
    - capabilities(): What can this provider do?
    - is_available(): Is the provider ready for use? (auto-detect via env vars)
    - build(): Build the project and return the artifact path.
    """

    name: str = "abstract"
    description: str = ""
    requires_setup: bool = False

    def __init__(self, config: ProjectConfig | None = None, **kwargs):
        self.config = config
        # Allow initialization from environment variables or kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return what this provider can do."""
        ...

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Check if the provider is ready to use. Returns (available, reason).

        Providers should auto-detect their environment by checking for environment
        variables that are only set in specific cloud CI environments.
        """
        ...

    @abstractmethod
    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        """Build the project. Returns a ProviderResult with the artifact path."""
        ...

    def sign(self, artifact: Path, config: ProjectConfig,
             **kwargs) -> ProviderResult:
        """Sign the artifact on the remote platform."""
        from ..sign import sign_artifact, SignResult
        # Remote providers delegate to local signing on the remote machine
        # The build command already includes signing
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
        """Install to a device."""
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
        """Upload to App Store Connect."""
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


def _is_in_ci() -> bool:
    """Check if we're running inside any CI environment."""
    ci_vars = [
        "CI", "GITHUB_ACTIONS", "GITHUB_ACTIONS_CI",
        "JENKINS_URL", "CIRCLECI", "TRAVIS", "GITLAB_CI",
        "BITRISE_IO", "CODEMAGIC_CI", "NEVERCODE", "BUILDKITE",
        "TEAMCITY_VERSION", "BAMBOO_BUILD",
    ]
    return any(os.environ.get(v) for v in ci_vars)


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
        if check_tool("clang") is None:
            return False, "clang not found. Install: apt install clang"
        from ..build.cpp import _find_mach_o_linker
        if _find_mach_o_linker() is None:
            return False, "No Mach-O linker (ld64.lld or cctools). Install: apt install lld"
        return True, "Local toolchain available"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        from .orchestrator import BuildOrchestrator
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
# SSHProvider — runs on a remote Mac via SSH
# ============================================================

class SSHProvider(BuildProvider):
    """Runs the build/sign/install pipeline on a remote Mac via SSH."""

    name = "ssh"
    description = "Run the pipeline on a remote Mac via SSH"

    def __init__(self, config: ProjectConfig | None = None, **kwargs):
        super().__init__(config)
        self.host = kwargs.get("host") or os.environ.get("SMART_APPLE_DEV_SSH_HOST")
        self.port = int(kwargs.get("port", 22) or os.environ.get("SMART_APPLE_DEV_SSH_PORT", 22))
        self.username = kwargs.get("username") or os.environ.get("SMART_APPLE_DEV_SSH_USERNAME")
        self.key_path = Path(kwargs.get("key_path", "") or os.environ.get("SMART_APPLE_DEV_SSH_KEY_PATH", "")) or None
        self.password = kwargs.get("password") or os.environ.get("SMART_APPLE_DEV_SSH_PASSWORD")
        self.timeout = int(kwargs.get("timeout", 30) or os.environ.get("SMART_APPLE_DEV_SSH_TIMEOUT", 30))

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not self.host:
            return False, "SSH host not configured. Set --host or SMART_APPLE_DEV_SSH_HOST."
        try:
            import paramiko
        except ImportError:
            return False, "paramiko not installed. Install with: pip install paramiko"
        if not self.username:
            return False, "SSH username not configured. Set --username or SMART_APPLE_DEV_SSH_USERNAME."
        if not self.key_path and not self.password:
            return False, "SSH auth not configured. Set --key-path/--password or SMART_APPLE_DEV_SSH_KEY_PATH/SMART_APPLE_DEV_SSH_PASSWORD."
        if self.key_path and not self.key_path.exists():
            return False, f"SSH key file not found: {self.key_path}"
        return True, "SSH provider configured"

    def _ssh_client(self) -> Any:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.key_path and self.key_path.exists():
            client.connect(
                hostname=self.host, port=self.port, username=self.username,
                key_filename=str(self.key_path), timeout=self.timeout,
            )
        elif self.password:
            client.connect(
                hostname=self.host, port=self.port, username=self.username,
                password=self.password, timeout=self.timeout,
            )
        else:
            raise ValueError("No SSH authentication method available")
        return client

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        import paramiko
        from time import perf_counter

        start = perf_counter()
        try:
            client = self._ssh_client()
        except paramiko.SSHException as e:
            return ProviderResult(success=False, errors=[f"SSH connection failed: {e}"])

        try:
            # Create remote work directory
            stdin, stdout, stderr = client.exec_command("mktemp -d")
            remote_work_dir = stdout.read().decode().strip()
            if not remote_work_dir:
                return ProviderResult(success=False, errors=["Failed to create remote work directory"])

            try:
                # Upload project
                sftp = client.open_sftp()
                for item in project_dir.rglob("*"):
                    if item.is_file():
                        remote_item = f"{remote_work_dir}/project/{item.relative_to(project_dir)}"
                        try:
                            sftp.put(str(item), remote_item)
                        except Exception:
                            pass  # Best effort
                sftp.close()

                # Run build
                build_cmd = f"cd {remote_work_dir}/project && smart-apple-dev build --target {target}"
                if release:
                    build_cmd += " --release"

                stdin, stdout, stderr = client.exec_command(build_cmd, timeout=600)
                exit_status = stdout.channel.recv_exit_status()
                stdout_data = stdout.read().decode()
                stderr_data = stderr.read().decode()

                if exit_status != 0:
                    return ProviderResult(
                        success=False,
                        output=stdout_data,
                        errors=[stderr_data or f"Remote build failed (exit code {exit_status})"],
                    )

                # Download artifact
                duration = perf_counter() - start
                return ProviderResult(
                    success=True,
                    output=stdout_data,
                    duration_seconds=duration,
                    metadata={"language": config.language, "provider": "ssh"},
                )
            finally:
                client.exec_command(f"rm -rf {remote_work_dir}")
                client.close()
        except Exception as e:
            return ProviderResult(success=False, errors=[f"Unexpected error: {e}"])


# ============================================================
# GitHubActionsProvider — runs on GitHub Actions macOS runners
# ============================================================

class GitHubActionsProvider(BuildProvider):
    """Runs the pipeline on GitHub Actions macOS runners."""

    name = "github-actions"
    description = "Run the pipeline on GitHub Actions macOS runners"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            return False, "Not running in GitHub Actions. Set GITHUB_ACTIONS=true."
        runner_os = os.environ.get("RUNNER_OS", "").lower()
        if runner_os != "macos":
            return False, f"GitHub Actions runner is {runner_os or 'unknown'}, macOS required."
        return True, f"Running on GitHub Actions macOS runner ({runner_os})"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        # On GitHub Actions, we run locally (the runner IS the Mac)
        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        success = exit_code == 0 if (exit_code := orch_result[0]) == 0 else False

        return ProviderResult(
            success=success,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "github-actions"},
        )


# ============================================================
# AWSMacProvider — runs on AWS EC2 Mac instances
# ============================================================

class AWSMacProvider(BuildProvider):
    """Runs the pipeline on AWS EC2 Mac instances."""

    name = "aws-mac"
    description = "Run the pipeline on AWS EC2 Mac instances"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=1.08,  # $1.08/hour for mac1 instance
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("AWS_EXECUTION_ENV") and not os.environ.get("AWS_REGION"):
            return False, "Not running on AWS. Set AWS_REGION and AWS_ACCESS_KEY_ID."
        if not check_tool("aws"):
            return False, "AWS CLI not found. Install with: pip install awscli"
        return True, "AWS environment detected"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        instance_id = os.environ.get("AWS_EC2_INSTANCE_ID")
        if not instance_id:
            return ProviderResult(
                success=False,
                errors=["AWS_EC2_INSTANCE_ID not set. Not running on EC2."],
            )

        import time
        start = time.perf_counter()

        # If running on an EC2 Mac instance, build locally
        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "aws-mac", "instance": instance_id},
        )


# ============================================================
# AzureMacProvider — runs on Azure macOS agents
# ============================================================

class AzureMacProvider(BuildProvider):
    """Runs the pipeline on Azure DevOps macOS agents."""

    name = "azure-mac"
    description = "Run the pipeline on Azure DevOps macOS agents"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("TF_BUILD"):
            return False, "Not running in Azure DevOps. Set TF_BUILD=true."
        agent_os = os.environ.get("AGENT_OS", "").lower()
        if "darwin" not in agent_os:
            return False, f"Azure agent OS is {agent_os}, macOS required."
        return True, f"Running on Azure DevOps macOS agent"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "azure-mac"},
        )


# ============================================================
# CircleCIMacProvider — runs on CircleCI macOS executors
# ============================================================

class CircleCIMacProvider(BuildProvider):
    """Runs the pipeline on CircleCI macOS executors."""

    name = "circleci-mac"
    description = "Run the pipeline on CircleCI macOS executors"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("CIRCLECI"):
            return False, "Not running in CircleCI. Set CIRCLECI=true."
        executor = os.environ.get("CIRCLE_JOB", "")
        return True, f"Running on CircleCI executor ({executor})"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "circleci-mac"},
        )


# ============================================================
# MacStadiumProvider — runs on MacStadium dedicated Macs
# ============================================================

class MacStadiumProvider(BuildProvider):
    """Runs the pipeline on MacStadium dedicated Mac machines."""

    name = "macstadium"
    description = "Run the pipeline on MacStadium dedicated Mac machines"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=30.0,  # ~$30/month minimum
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        host = os.environ.get("SMART_APPLE_DEV_MACSTADIUM_HOST")
        if not host:
            return False, "MacStadium host not configured. Set SMART_APPLE_DEV_MACSTADIUM_HOST."
        return True, "MacStadium provider configured"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        # Delegate to SSH provider
        ssh = SSHProvider(
            host=os.environ.get("SMART_APPLE_DEV_MACSTADIUM_HOST"),
            username=os.environ.get("SMART_APPLE_DEV_MACSTADIUM_USER"),
            key_path=Path(os.environ.get("SMART_APPLE_DEV_MACSTADIUM_KEY", "")),
        )
        return ssh.build(project_dir, config, target, release)


# ============================================================
# CodemagicProvider — runs on Codemagic CI/CD
# ============================================================

class CodemagicProvider(BuildProvider):
    """Runs the pipeline on Codemagic CI/CD platform."""

    name = "codemagic"
    description = "Run the pipeline on Codemagic CI/CD"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("CODEMAGIC") and not os.environ.get("CM_BUILD_ID"):
            return False, "Not running in Codemagic. Set CODEMAGIC=true or CM_BUILD_ID."
        return True, f"Running in Codemagic (build {os.environ.get('CM_BUILD_ID', 'unknown')})"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "codemagic"},
        )


# ============================================================
# BitriseProvider — runs on Bitrise CI/CD
# ============================================================

class BitriseProvider(BuildProvider):
    """Runs the pipeline on Bitrise CI/CD platform."""

    name = "bitrise"
    description = "Run the pipeline on Bitrise CI/CD"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("BITRISE_IO"):
            return False, "Not running in Bitrise. Set BITRISE_IO=true."
        return True, f"Running in Bitrise (workflow: {os.environ.get('BITRISE_TRIGGERED_WORKFLOW_TITLE', 'unknown')})"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "bitrise"},
        )


# ============================================================
# JenkinsMacProvider — runs on Jenkins macOS agents
# ============================================================

class JenkinsMacProvider(BuildProvider):
    """Runs the pipeline on Jenkins macOS agents."""

    name = "jenkins"
    description = "Run the pipeline on Jenkins macOS agents"

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
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("JENKINS_URL"):
            return False, "Not running in Jenkins. Set JENKINS_URL."
        return True, f"Running in Jenkins (URL: {os.environ.get('JENKINS_URL')})"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "jenkins"},
        )


# ============================================================
# BuildJetProvider — runs on BuildJet cloud Mac runners
# ============================================================

class BuildJetProvider(BuildProvider):
    """Runs the pipeline on BuildJet cloud Mac runners."""

    name = "buildjet"
    description = "Run the pipeline on BuildJet cloud Mac runners"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.045,  # ~$0.045/min
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("BUIlDJET_CI") and not os.environ.get("BUILDJET_CI"):
            return False, "Not running in BuildJet. Set BUILDJET_CI=true."
        return True, "Running in BuildJet"

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "buildjet"},
        )


# ============================================================
# NevercodeProvider — runs on Nevercode CI/CD
# ============================================================

class NevercodeProvider(BuildProvider):
    """Runs the pipeline on Nevercode CI/CD platform."""

    name = "nevercode"
    description = "Run the pipeline on Nevercode CI/CD"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            build=True,
            sign=True,
            install=True,
            upload=True,
            languages=["swift", "objc", "cpp", "rust", "go", "kotlin"],
            targets=["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"],
            requires_internet=True,
            cost_per_build=0.0,
            platform="macos",
        )

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("NEVERCODE") and not os.environ.get("LC_ALL"):
            # Nevercode doesn't set standard env vars but we detect it
            pass
        # Check for common Nevercode environment variable
        if os.environ.get("BUILD_STATUS") and os.environ.get("APP_ID"):
            return True, "Running in Nevercode"
        return False, "Not running in Nevercode."

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        if not self.is_available()[0]:
            return ProviderResult(success=False, errors=[self.is_available()[1]])

        import time
        start = time.perf_counter()

        orch_result = run_cmd(
            ["smart-apple-dev", "build", "--target", target] +
            (["--release"] if release else []),
            cwd=project_dir,
            timeout=600,
        )

        duration = time.perf_counter() - start
        exit_code = orch_result[0]

        return ProviderResult(
            success=exit_code == 0,
            output=orch_result[1],
            errors=[orch_result[2]] if orch_result[2] and exit_code != 0 else [],
            duration_seconds=duration,
            metadata={"language": config.language, "provider": "nevercode"},
        )


# ============================================================
# Registry
# ============================================================

class ProviderRegistry:
    """Registry of available providers."""

    def __init__(self):
        self._providers: dict[str, BuildProvider] = {}
        self._load_providers()

    def _load_providers(self):
        """Auto-discover all built-in providers."""
        from .ssh_provider import SSHProvider

        # Register all built-in providers
        self.register(LocalProvider())
        self.register(SSHProvider())
        self.register(GitHubActionsProvider())
        self.register(AWSMacProvider())
        self.register(AzureMacProvider())
        self.register(CircleCIMacProvider())
        self.register(MacStadiumProvider())
        self.register(CodemagicProvider())
        self.register(BitriseProvider())
        self.register(JenkinsMacProvider())
        self.register(BuildJetProvider())
        self.register(NevercodeProvider())

    def register(self, provider: BuildProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> BuildProvider | None:
        return self._providers.get(name)

    def list_available(self) -> list[BuildProvider]:
        """Return only providers that are currently available (auto-detected)."""
        return [p for p in self._providers.values() if p.is_available()[0]]

    def list_all(self) -> list[BuildProvider]:
        return list(self._providers.values())

    def get_default(self) -> BuildProvider:
        """Get the first available provider, or LocalProvider as fallback."""
        available = self.list_available()
        if available:
            # Prefer local provider if available
            local = self.get("local")
            if local and local.is_available()[0]:
                return local
            return available[0]
        return self.get("local") or LocalProvider()

    def get_by_platform(self, platform: str = "any") -> list[BuildProvider]:
        """Get providers that support a specific platform (macos, ios, any)."""
        results = []
        for p in self._providers.values():
            caps = p.capabilities()
            if platform == "any" or caps.platform == "any" or platform in caps.platform:
                results.append(p)
        return results


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
            available = list(reg._providers.keys())
            raise ValueError(
                f"Unknown provider: '{name}'. Available: {available}. "
                f"Run 'smart-apple-dev provider list' to see all providers."
            )
        return p
    return reg.get_default()


def auto_detect_provider() -> BuildProvider:
    """Auto-detect the best available provider based on the current environment.

    Checks all registered providers' is_available() and returns the most appropriate one.
    Falls back to LocalProvider if nothing else is available.
    """
    reg = get_registry()
    available = reg.list_available()
    if not available:
        return LocalProvider()
    # Prefer local provider in non-CI environments
    if not _is_in_ci():
        local = reg.get("local")
        if local and local.is_available()[0]:
            return local
    return available[0]
