"""Tests for smartapple.build.orchestrator."""
import os
from pathlib import Path

from smartapple.build.orchestrator import BuildOrchestrator, BuildResult, run_cmd


def test_orchestrator_list_backends():
    orch = BuildOrchestrator()
    backends = orch.list_backends()
    assert "swift" in backends
    assert "cpp" in backends
    assert "objc" in backends
    assert "rust" in backends
    assert "go" in backends
    assert "kotlin" in backends


def test_orchestrator_get_backend():
    orch = BuildOrchestrator()
    assert orch._get_backend("swift") == "swift"
    assert orch._get_backend("objective-c") == "objc"
    assert orch._get_backend("c++") == "cpp"
    assert orch._get_backend("c") == "cpp"
    assert orch._get_backend("rust") == "rust"
    assert orch._get_backend("go") == "go"
    assert orch._get_backend("kotlin") == "kotlin"


def test_orchestrator_check_backend():
    orch = BuildOrchestrator()
    info = orch.check_backend_availability("swift")
    assert info["backend"] == "swift"
    assert "xtool" in info["checks"] or "swift" in info["checks"]


def test_run_cmd_success():
    code, out, err = run_cmd(["echo", "hello"], timeout=5)
    assert code == 0
    assert "hello" in out


def test_run_cmd_failure():
    code, out, err = run_cmd(["false"], timeout=5)
    assert code != 0


def test_run_cmd_timeout_short():
    code, out, err = run_cmd(["sleep", "5"], timeout=1)
    assert code == -1
    assert "timed out" in err or "timeout" in err.lower()


def test_run_cmd_not_found():
    code, out, err = run_cmd(["definitely_not_a_command_xyz123"], timeout=5)
    assert code == -1
    assert "not found" in err
