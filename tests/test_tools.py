"""Tests for agent tools in smartapple.agent.tools."""

from __future__ import annotations

import pytest
from smartapple.agent.tools import check_shell_safe, tool_run_shell


def test_check_shell_safe_empty():
    safe, reason = check_shell_safe("")
    assert not safe
    assert "Empty" in reason

    safe, reason = check_shell_safe("   ")
    assert not safe
    assert "Empty" in reason


def test_check_shell_safe_blocklist():
    safe, reason = check_shell_safe("echo hello; rm -rf /")
    assert not safe
    assert "Blocked pattern" in reason


def test_check_shell_safe_allowlist():
    safe, reason = check_shell_safe("echo hello")
    assert safe
    assert reason == "ok"

    safe, reason = check_shell_safe("unallowed_binary --flag")
    assert not safe
    assert "not in allowlist" in reason


def test_tool_run_shell_valid():
    res = tool_run_shell({"command": "echo hello world"})
    assert "hello world" in res
    assert "[exit code: 0]" in res


def test_tool_run_shell_command_injection_mitigated():
    # Attempting shell chaining or command substitution
    # With shell=False, arguments like '; echo injected' are passed as literal arguments to 'echo'
    res = tool_run_shell({"command": "echo hello; echo injected"})
    # It should print 'hello; echo injected' on a single stdout line, rather than running two separate commands
    lines = res.splitlines()
    assert lines[0] == "hello; echo injected"
    assert lines[-1] == "[exit code: 0]"


def test_tool_run_shell_blocked():
    res = tool_run_shell({"command": "unknown_command_12345"})
    assert "Error: Command not allowed" in res
