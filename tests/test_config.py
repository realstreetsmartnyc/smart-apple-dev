"""Tests for smartapple.core.config."""
from pathlib import Path

from smartapple.core.config import (
    ProjectConfig,
    find_project_root,
    load_config,
    get_platform,
    ensure_dirs,
    check_tool,
)


def test_default_config():
    cfg = ProjectConfig()
    assert cfg.name == "my-app"
    assert cfg.language == "swift"
    assert cfg.bundle_id == "com.example.app"
    assert cfg.target == "ios"


def test_to_toml_round_trip():
    cfg = ProjectConfig(name="hello", language="rust", bundle_id="com.x.y")
    toml_str = cfg.to_toml()
    assert "[project]" in toml_str
    assert 'name = "hello"' in toml_str
    assert 'language = "rust"' in toml_str


def test_from_dict():
    data = {"project": {"name": "abc", "language": "go"}}
    cfg = ProjectConfig.from_dict(data)
    assert cfg.name == "abc"
    assert cfg.language == "go"
    assert cfg.bundle_id == "com.example.app"


def test_to_toml_with_signing():
    cfg = ProjectConfig(name="x", signing={"identity": "Apple Dev", "team": "ABCDE12345"})
    out = cfg.to_toml()
    assert "[signing]" in out
    assert 'identity = "Apple Dev"' in out


def test_find_project_root(tmp_path):
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    (tmp_path / "smartapple.toml").write_text('[project]\nname = "root"\n')

    root = find_project_root(sub)
    assert root == tmp_path


def test_find_project_root_none(tmp_path):
    sub = tmp_path / "nowhere"
    sub.mkdir()
    assert find_project_root(sub) is None


def test_get_platform():
    p = get_platform()
    assert p in ("linux", "macos", "windows", "unknown")


def test_ensure_dirs():
    dirs = ensure_dirs()
    for key in ("base", "sdk", "tools", "certs", "profiles", "build"):
        assert key in dirs
        assert dirs[key].exists()


def test_check_tool_missing():
    assert check_tool("definitely_not_a_real_tool_xyz") is None


def test_load_config_from_file(tmp_path):
    cfg_file = tmp_path / "smartapple.toml"
    cfg_file.write_text(
        '[project]\n'
        'name = "myapp"\n'
        'language = "swift"\n'
        'bundle_id = "com.test.app"\n'
        'version = "1.0.0"\n'
        'build_system = "swiftpm"\n'
        'min_os = "16.0"\n'
        'target = "ios"\n'
    )
    cfg = load_config(cfg_file)
    assert cfg.name == "myapp"
    assert cfg.min_os == "16.0"
