"""SSH build provider — runs commands on a remote Mac via SSH."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore

from .provider import BuildProvider, ProviderCapabilities, ProviderResult
from ..core.config import ProjectConfig
from ..core.sdk import list_installed_sdks
from ..build.orchestrator import BuildOrchestrator


@dataclass
class SSHProvider(BuildProvider):
    """Runs the build/sign/install pipeline on a remote Mac via SSH."""

    name = "ssh"
    description = "Run the pipeline on a remote Mac via SSH"

    host: str | None = None
    port: int = 22
    username: str | None = None
    key_path: Path | None = None
    password: str | None = None
    timeout: int = 30

    def __post_init__(self):
        # Ensure key_path is Path if set
        if self.key_path and isinstance(self.key_path, str):
            self.key_path = Path(self.key_path)

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
        )

    def is_available(self) -> tuple[bool, str]:
        if not self.host:
            return False, "SSH host not configured. Set --host or SSH_HOST environment variable."

        # Check for paramiko
        try:
            try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore
        except ImportError:
            return False, "paramiko not installed. Install with: pip install paramiko"

        # Validate we have auth method
        if not self.username:
            return False, "SSH username not configured. Set --username or SSH_USERNAME."

        if not self.key_path and not self.password:
            return (
                False,
                "SSH authentication not configured. Provide --key-path or --password (or SSH_KEY_PATH/SSH_PASSWORD).",
            )

        if self.key_path and not self.key_path.exists():
            return False, f"SSH key file not found: {self.key_path}"

        return True, "SSH provider configured"

    def _ssh_client(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if self.key_path and self.key_path.exists():
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                key_filename=str(self.key_path),
                timeout=self.timeout,
            )
        elif self.password:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
            )
        else:
            raise ValueError("No SSH authentication method available")

        return client

    def _scp_upload(self, client: paramiko.SSHClient, local_path: Path, remote_path: str):
        """Upload file or directory via SCP."""
        sftp = client.open_sftp()
        try:
            if local_path.is_file():
                sftp.put(str(local_path), remote_path)
            elif local_path.is_dir():
                # Create remote directory
                try:
                    sftp.stat(remote_path)
                except FileNotFoundError:
                    sftp.mkdir(remote_path)
                # Upload contents
                for item in local_path.rglob("*"):
                    if item.is_file():
                        remote_item = remote_path / item.relative_to(local_path)
                        sftp.put(str(item), str(remote_item))
        finally:
            sftp.close()

    def _scp_download(self, client: paramiko.SSHClient, remote_path: str, local_path: Path):
        """Download file or directory via SCP."""
        sftp = client.open_sftp()
        try:
            if sftp.lstat(remote_path).st_mode & 0o170000 == 0o040000:  # directory
                local_path.mkdir(parents=True, exist_ok=True)
                for item in sftp.listdir(remote_path):
                    remote_item = f"{remote_path}/{item}"
                    local_item = local_path / item
                    if sftp.lstat(remote_item).st_mode & 0o170000 == 0o040000:
                        self._scp_download(client, remote_item, local_item)
                    else:
                        sftp.get(remote_item, str(local_item))
            else:
                sftp.get(remote_path, str(local_path))
        finally:
            sftp.close()

    def build(self, project_dir: Path, config: ProjectConfig,
              target: str = "ios", release: bool = False) -> ProviderResult:
        """Build the project on a remote Mac via SSH."""
        if not self.is_available()[0]:
            return ProviderResult(
                success=False,
                errors=[self.is_available()[1]],
            )

        import time
        from paramiko import SSHException

        start = time.perf_counter()

        try:
            client = self._ssh_client()
        except SSHException as e:
            return ProviderResult(
                success=False,
                errors=[f"SSH connection failed: {e}"],
            )

        try:
            # Create temporary directory on remote
            stdin, stdout, stderr = client.exec_command("mktemp -d")
            remote_work_dir = stdout.read().decode().strip()
            if not remote_work_dir:
                return ProviderResult(
                    success=False,
                    errors=["Failed to create remote work directory"],
                )

            try:
                # Upload project to remote
                self._scp_upload(client, project_dir, f"{remote_work_dir}/project")

                # Build command
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
                        errors=[stderr_data or f"Remote build failed with exit code {exit_status}"],
                    )

                # Download artifact (we need to determine what was built)
                # The build command outputs the artifact path, so let's parse it
                # For now, we'll look in the standard build directory
                remote_build_dir = f"{remote_work_dir}/project/build/{config.name}"
                local_artifact_dir = project_dir / "build" / config.name
                local_artifact_dir.mkdir(parents=True, exist_ok=True)

                # Try to download the entire build directory
                self._scp_download(client, remote_build_dir, local_artifact_dir)

                # Find the actual artifact (simple heuristic)
                artifact = None
                for ext in [".app", ".ipa"]:
                    for file in local_artifact_dir.rglob(f"*{ext}"):
                        if file.is_file() or (ext == ".app" and file.is_dir()):
                            artifact = file
                            break
                    if artifact:
                        break

                duration = time.perf_counter() - start

                return ProviderResult(
                    success=True,
                    artifact=artifact,
                    output=stdout_data,
                    duration_seconds=duration,
                    metadata={"language": config.language, "provider": "ssh"},
                )
            finally:
                # Clean up remote directory
                try:
                    client.exec_command(f"rm -rf {remote_work_dir}")
                except Exception:
                    pass  # Best effort cleanup
                client.close()

        except Exception as e:
            return ProviderResult(
                success=False,
                errors=[f"Unexpected error: {e}"],
            )


def get_provider(name: str | None = None):
    """Get a provider by name, with SSH support."""
    from ..build.provider import get_provider as _get_provider

    if name == "ssh":
        return SSHProvider()

    return _get_provider(name)


# Register SSH provider with the registry
def _register_ssh_provider():
    from ..build.provider import get_registry
    registry = get_registry()
    registry.register(SSHProvider())


# Auto-register when module is imported
_register_ssh_provider()