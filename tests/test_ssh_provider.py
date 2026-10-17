"""Tests for smartapple.build.ssh_provider (SSHBuildProvider)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from paramiko import SSHException

from smartapple.build.provider import ProviderResult
from smartapple.build.ssh_provider import SSHProvider, get_provider
from smartapple.core.config import ProjectConfig


# -------------------------------------------------------------------
# Initialization & Capabilities
# -------------------------------------------------------------------

def test_ssh_provider_init_converts_str_key_path():
    provider = SSHProvider(
        host="example.com",
        username="user",
        key_path="/tmp/fake_key",
    )
    assert isinstance(provider.key_path, Path)
    assert provider.key_path == Path("/tmp/fake_key")


def test_ssh_provider_capabilities():
    provider = SSHProvider()
    caps = provider.capabilities()
    assert caps.build is True
    assert caps.sign is True
    assert caps.install is True
    assert caps.upload is True
    assert caps.requires_internet is True
    assert caps.cost_per_build == 0.0
    assert "swift" in caps.languages
    assert "ios" in caps.targets


# -------------------------------------------------------------------
# is_available
# -------------------------------------------------------------------

def test_is_available_missing_host():
    provider = SSHProvider(host=None, username="user", password="secret")
    ok, reason = provider.is_available()
    assert ok is False
    assert "host not configured" in reason.lower()


def test_is_available_missing_paramiko():
    provider = SSHProvider(host="example.com", username="user", password="secret")
    with patch("smartapple.build.ssh_provider.paramiko", None):
        ok, reason = provider.is_available()
        assert ok is False
        assert "paramiko not installed" in reason.lower()


def test_is_available_missing_username():
    provider = SSHProvider(host="example.com", username=None, password="secret")
    ok, reason = provider.is_available()
    assert ok is False
    assert "username not configured" in reason.lower()


def test_is_available_missing_auth():
    provider = SSHProvider(host="example.com", username="user", key_path=None, password=None)
    ok, reason = provider.is_available()
    assert ok is False
    assert "authentication not configured" in reason.lower()


def test_is_available_key_file_not_found():
    provider = SSHProvider(host="example.com", username="user", key_path="/nonexistent/key")
    ok, reason = provider.is_available()
    assert ok is False
    assert "ssh key file not found" in reason.lower()


def test_is_available_with_password():
    provider = SSHProvider(host="example.com", username="user", password="secret")
    ok, reason = provider.is_available()
    assert ok is True
    assert "ssh provider configured" in reason.lower()


def test_is_available_with_existing_key(tmp_path):
    key_file = tmp_path / "id_rsa"
    key_file.write_text("fake_key")
    provider = SSHProvider(host="example.com", username="user", key_path=key_file)
    ok, reason = provider.is_available()
    assert ok is True
    assert "ssh provider configured" in reason.lower()


# -------------------------------------------------------------------
# _ssh_client
# -------------------------------------------------------------------

def test_ssh_client_connects_with_key(tmp_path):
    key_file = tmp_path / "id_rsa"
    key_file.write_text("fake_key")
    provider = SSHProvider(
        host="example.com",
        port=2222,
        username="admin",
        key_path=key_file,
        timeout=15,
    )

    with patch("smartapple.build.ssh_provider.paramiko.SSHClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = provider._ssh_client()

        assert client is mock_client
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once_with(
            hostname="example.com",
            port=2222,
            username="admin",
            key_filename=str(key_file),
            timeout=15,
        )


def test_ssh_client_connects_with_password():
    provider = SSHProvider(
        host="example.com",
        port=22,
        username="admin",
        password="password123",
        timeout=10,
    )

    with patch("smartapple.build.ssh_provider.paramiko.SSHClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = provider._ssh_client()

        assert client is mock_client
        mock_client.connect.assert_called_once_with(
            hostname="example.com",
            port=22,
            username="admin",
            password="password123",
            timeout=10,
        )


def test_ssh_client_no_auth_raises():
    provider = SSHProvider(host="example.com", username="admin")
    # Manually bypass is_available check to hit ValueError
    with patch("smartapple.build.ssh_provider.paramiko.SSHClient"):
        with pytest.raises(ValueError) as exc_info:
            provider._ssh_client()
        assert "No SSH authentication method available" in str(exc_info.value)


# -------------------------------------------------------------------
# _scp_upload & _scp_download
# -------------------------------------------------------------------

def test_scp_upload_file(tmp_path):
    provider = SSHProvider()
    local_file = tmp_path / "test.txt"
    local_file.write_text("content")

    mock_sftp = MagicMock()
    mock_client = MagicMock()
    mock_client.open_sftp.return_value = mock_sftp

    provider._scp_upload(mock_client, local_file, "/remote/test.txt")

    mock_sftp.put.assert_called_once_with(str(local_file), "/remote/test.txt")
    mock_sftp.close.assert_called_once()


def test_scp_upload_directory(tmp_path):
    provider = SSHProvider()
    project_dir = tmp_path / "Project"
    project_dir.mkdir()
    sub_dir = project_dir / "sub"
    sub_dir.mkdir()
    file1 = project_dir / "file1.txt"
    file1.write_text("f1")
    file2 = sub_dir / "file2.txt"
    file2.write_text("f2")

    mock_sftp = MagicMock()
    # First stat for /remote/project raises FileNotFoundError
    # Then stat for /remote/project/sub raises FileNotFoundError
    def mock_stat(path):
        if path in ["/remote/project", "/remote/project/sub"]:
            raise FileNotFoundError()
        return MagicMock()

    mock_sftp.stat.side_effect = mock_stat

    mock_client = MagicMock()
    mock_client.open_sftp.return_value = mock_sftp

    provider._scp_upload(mock_client, project_dir, "/remote/project")

    # Verify directory creations
    assert mock_sftp.mkdir.call_count >= 1
    # Verify file uploads
    put_calls = [call[0] for call in mock_sftp.put.call_args_list]
    assert (str(file1), "/remote/project/file1.txt") in put_calls
    assert (str(file2), "/remote/project/sub/file2.txt") in put_calls
    mock_sftp.close.assert_called_once()


def test_scp_download_file(tmp_path):
    provider = SSHProvider()
    local_file = tmp_path / "downloaded.txt"

    mock_sftp = MagicMock()
    # File st_mode (regular file)
    mock_stat = MagicMock()
    mock_stat.st_mode = 0o100644
    mock_sftp.lstat.return_value = mock_stat

    mock_client = MagicMock()
    mock_client.open_sftp.return_value = mock_sftp

    provider._scp_download(mock_client, "/remote/file.txt", local_file)

    mock_sftp.get.assert_called_once_with("/remote/file.txt", str(local_file))
    mock_sftp.close.assert_called_once()


def test_scp_download_directory(tmp_path):
    provider = SSHProvider()
    local_dir = tmp_path / "download_dir"

    mock_sftp = MagicMock()

    dir_stat = MagicMock()
    dir_stat.st_mode = 0o040755

    file_stat = MagicMock()
    file_stat.st_mode = 0o100644

    def mock_lstat(path):
        if path in ["/remote/build", "/remote/build/subdir"]:
            return dir_stat
        return file_stat

    mock_sftp.lstat.side_effect = mock_lstat

    def mock_listdir(path):
        if path == "/remote/build":
            return ["subdir", "app.app"]
        if path == "/remote/build/subdir":
            return ["nested.txt"]
        return []

    mock_sftp.listdir.side_effect = mock_listdir

    mock_client = MagicMock()
    mock_client.open_sftp.return_value = mock_sftp

    provider._scp_download(mock_client, "/remote/build", local_dir)

    get_calls = [call[0] for call in mock_sftp.get.call_args_list]
    assert ("/remote/build/app.app", str(local_dir / "app.app")) in get_calls
    assert ("/remote/build/subdir/nested.txt", str(local_dir / "subdir" / "nested.txt")) in get_calls


# -------------------------------------------------------------------
# build
# -------------------------------------------------------------------

def test_build_returns_error_when_unavailable():
    provider = SSHProvider(host=None)
    config = ProjectConfig(name="TestApp", language="swift")
    result = provider.build(Path("/tmp/proj"), config)
    assert result.success is False
    assert "host not configured" in result.errors[0].lower()


def test_build_ssh_connection_failed():
    provider = SSHProvider(host="example.com", username="user", password="pwd")
    config = ProjectConfig(name="TestApp", language="swift")

    with patch.object(provider, "_ssh_client", side_effect=SSHException("Auth failed")):
        result = provider.build(Path("/tmp/proj"), config)
        assert result.success is False
        assert "ssh connection failed: auth failed" in result.errors[0].lower()


def test_build_mktemp_failed(tmp_path):
    provider = SSHProvider(host="example.com", username="user", password="pwd")
    config = ProjectConfig(name="TestApp", language="swift")

    mock_client = MagicMock()
    # exec_command("mktemp -d")
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b""  # Empty work dir
    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, MagicMock())

    with patch.object(provider, "_ssh_client", return_value=mock_client):
        result = provider.build(tmp_path, config)
        assert result.success is False
        assert "failed to create remote work directory" in result.errors[0].lower()


def test_build_remote_command_failed(tmp_path):
    provider = SSHProvider(host="example.com", username="user", password="pwd")
    config = ProjectConfig(name="TestApp", language="swift")

    mock_client = MagicMock()

    # Call 1: mktemp -d
    mock_stdout_mktemp = MagicMock()
    mock_stdout_mktemp.read.return_value = b"/tmp/remote_tmp_123\n"

    # Call 2: smart-apple-dev build
    mock_stdout_build = MagicMock()
    mock_stdout_build.channel.recv_exit_status.return_value = 1
    mock_stdout_build.read.return_value = b"Building..."

    mock_stderr_build = MagicMock()
    mock_stderr_build.read.return_value = b"Compilation error"

    mock_client.exec_command.side_effect = [
        (MagicMock(), mock_stdout_mktemp, MagicMock()),
        (MagicMock(), mock_stdout_build, mock_stderr_build),
        (MagicMock(), MagicMock(), MagicMock()),  # rm -rf
    ]

    with patch.object(provider, "_ssh_client", return_value=mock_client):
        with patch.object(provider, "_scp_upload"):
            result = provider.build(tmp_path, config, target="ios", release=True)

            assert result.success is False
            assert "compilation error" in result.errors[0].lower()
            assert result.output == "Building..."

            # Verify build_cmd included --release
            exec_calls = mock_client.exec_command.call_args_list
            build_cmd_arg = exec_calls[1][0][0]
            assert "--target ios" in build_cmd_arg
            assert "--release" in build_cmd_arg

            # Verify cleanup was called
            cleanup_cmd_arg = exec_calls[2][0][0]
            assert "rm -rf /tmp/remote_tmp_123" in cleanup_cmd_arg
            mock_client.close.assert_called_once()


def test_build_success(tmp_path):
    provider = SSHProvider(host="example.com", username="user", password="pwd")
    config = ProjectConfig(name="TestApp", language="swift")

    mock_client = MagicMock()

    # Call 1: mktemp -d
    mock_stdout_mktemp = MagicMock()
    mock_stdout_mktemp.read.return_value = b"/tmp/remote_tmp_123\n"

    # Call 2: smart-apple-dev build
    mock_stdout_build = MagicMock()
    mock_stdout_build.channel.recv_exit_status.return_value = 0
    mock_stdout_build.read.return_value = b"Build Succeeded"

    mock_stderr_build = MagicMock()
    mock_stderr_build.read.return_value = b""

    mock_client.exec_command.side_effect = [
        (MagicMock(), mock_stdout_mktemp, MagicMock()),
        (MagicMock(), mock_stdout_build, mock_stderr_build),
        (MagicMock(), MagicMock(), MagicMock()),  # rm -rf
    ]

    def fake_download(client, remote_path, local_path):
        # Create a fake .app artifact in local_path
        app_dir = local_path / "TestApp.app"
        app_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(provider, "_ssh_client", return_value=mock_client):
        with patch.object(provider, "_scp_upload"):
            with patch.object(provider, "_scp_download", side_effect=fake_download):
                result = provider.build(tmp_path, config, target="ios", release=False)

                assert result.success is True
                assert result.output == "Build Succeeded"
                assert result.artifact is not None
                assert result.artifact.name == "TestApp.app"
                assert result.duration_seconds > 0
                assert result.metadata["provider"] == "ssh"
                assert result.metadata["language"] == "swift"

                mock_client.close.assert_called_once()


def test_build_handles_unexpected_exception(tmp_path):
    provider = SSHProvider(host="example.com", username="user", password="pwd")
    config = ProjectConfig(name="TestApp", language="swift")

    with patch.object(provider, "_ssh_client", side_effect=RuntimeError("System failure")):
        result = provider.build(tmp_path, config)
        assert result.success is False
        assert "unexpected error: system failure" in result.errors[0].lower()


# -------------------------------------------------------------------
# get_provider registration
# -------------------------------------------------------------------

def test_get_provider_ssh():
    p = get_provider("ssh")
    assert isinstance(p, SSHProvider)
    assert p.name == "ssh"
