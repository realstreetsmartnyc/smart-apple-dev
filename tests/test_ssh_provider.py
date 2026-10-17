"""Tests for SSHProvider, specifically testing artifact detection."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from smartapple.build.ssh_provider import SSHProvider
from smartapple.core.config import ProjectConfig


def test_ssh_provider_capabilities():
    p = SSHProvider()
    caps = p.capabilities()
    assert caps.build is True
    assert caps.sign is True
    assert caps.install is True
    assert caps.upload is True
    assert "swift" in caps.languages
    assert caps.requires_internet is True


def test_ssh_provider_is_available():
    p = SSHProvider()
    avail, reason = p.is_available()
    assert avail is False
    assert "host not configured" in reason.lower()

    p.host = "example.com"
    avail, reason = p.is_available()
    assert avail is False
    assert "username not configured" in reason.lower()

    p.username = "user"
    avail, reason = p.is_available()
    assert avail is False
    assert "authentication not configured" in reason.lower()

    p.password = "secret"
    avail, reason = p.is_available()
    assert avail is True
    assert "configured" in reason.lower()


def test_ssh_provider_build_finds_app_dir_artifact(tmp_path):
    p = SSHProvider(host="example.com", username="user", password="pwd")
    project_dir = tmp_path / "MyProject"
    project_dir.mkdir()
    config = ProjectConfig(name="MyApp", language="swift")

    local_artifact_dir = project_dir / "build" / "MyApp"
    app_dir = local_artifact_dir / "Release" / "MyApp.app"
    app_dir.mkdir(parents=True)

    mock_client = MagicMock()
    mock_stdout_mktemp = MagicMock()
    mock_stdout_mktemp.read.return_value = b"/tmp/remote_dir\n"

    mock_stdout_cmd = MagicMock()
    mock_stdout_cmd.channel.recv_exit_status.return_value = 0
    mock_stdout_cmd.read.return_value = b"Build output"

    mock_stderr_cmd = MagicMock()
    mock_stderr_cmd.read.return_value = b""

    mock_client.exec_command.side_effect = [
        (MagicMock(), mock_stdout_mktemp, MagicMock()),
        (MagicMock(), mock_stdout_cmd, mock_stderr_cmd),
        (MagicMock(), MagicMock(), MagicMock()),  # rm -rf
    ]

    with patch.object(p, "_ssh_client", return_value=mock_client), \
         patch.object(p, "_scp_upload"), \
         patch.object(p, "_scp_download"):

        res = p.build(project_dir, config)
        assert res.success is True
        assert res.artifact == app_dir


def test_ssh_provider_build_finds_ipa_artifact(tmp_path):
    p = SSHProvider(host="example.com", username="user", password="pwd")
    project_dir = tmp_path / "MyProject"
    project_dir.mkdir()
    config = ProjectConfig(name="MyApp", language="swift")

    local_artifact_dir = project_dir / "build" / "MyApp"
    local_artifact_dir.mkdir(parents=True)
    ipa_file = local_artifact_dir / "Release" / "MyApp.ipa"
    ipa_file.parent.mkdir(parents=True, exist_ok=True)
    ipa_file.write_text("dummy ipa")

    mock_client = MagicMock()
    mock_stdout_mktemp = MagicMock()
    mock_stdout_mktemp.read.return_value = b"/tmp/remote_dir\n"

    mock_stdout_cmd = MagicMock()
    mock_stdout_cmd.channel.recv_exit_status.return_value = 0
    mock_stdout_cmd.read.return_value = b"Build output"

    mock_stderr_cmd = MagicMock()
    mock_stderr_cmd.read.return_value = b""

    mock_client.exec_command.side_effect = [
        (MagicMock(), mock_stdout_mktemp, MagicMock()),
        (MagicMock(), mock_stdout_cmd, mock_stderr_cmd),
        (MagicMock(), MagicMock(), MagicMock()),
    ]

    with patch.object(p, "_ssh_client", return_value=mock_client), \
         patch.object(p, "_scp_upload"), \
         patch.object(p, "_scp_download"):

        res = p.build(project_dir, config)
        assert res.success is True
        assert res.artifact == ipa_file
