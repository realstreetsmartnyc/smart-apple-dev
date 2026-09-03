"""Tests for the visual UI helper module.

Run with ``SMART_APPLE_DEV_NO_COLOR=1`` so the ASCII glyphs (``[OK]`` etc.)
are exercised instead of the rich colour/emoji path. That makes assertions
straightforward and avoids platform-specific ANSI differences.
"""

from __future__ import annotations

import os
import time
from unittest import mock

# Force plain glyphs for the test session.
os.environ.setdefault("SMART_APPLE_DEV_NO_COLOR", "1")

import pytest

# Reset the lazy singleton so the env var is respected
from smartapple import ui
ui._CONSOLE_SINGLETON = None


class TestGlyphs:
    def test_glyphs_are_strings(self):
        for attr in ("OK", "FAIL", "WARN", "INFO", "HINT", "ARROW", "BULLET"):
            assert isinstance(getattr(ui.Glyph, attr), str)
            assert len(getattr(ui.Glyph, attr)) > 0


class TestWantColor:
    def test_no_color_env(self, monkeypatch):
        monkeypatch.setenv("SMART_APPLE_DEV_NO_COLOR", "1")
        assert ui._want_color() is False

    def test_force_color_env(self, monkeypatch):
        monkeypatch.setenv("SMART_APPLE_DEV_NO_COLOR", "0")
        monkeypatch.setenv("SMART_APPLE_DEV_FORCE_COLOR", "1")
        # Reset cached singleton so the new env vars take effect
        monkeypatch.setattr(ui, "_CONSOLE_SINGLETON", None)
        assert ui._want_color() is True


class TestStatusHelpers:
    def test_success(self, capsys):
        ui.success("it worked")
        out = capsys.readouterr().out
        assert "it worked" in out
        assert "[OK]" in out or "\u2705" in out

    def test_error_goes_to_stderr(self, capsys):
        ui.error("something broke")
        out, err = capsys.readouterr()
        assert "something broke" in err
        assert out == ""

    def test_warning(self, capsys):
        ui.warning("be careful")
        out = capsys.readouterr().out
        assert "be careful" in out

    def test_info(self, capsys):
        ui.info("hello")
        out = capsys.readouterr().out
        assert "hello" in out

    def test_hint(self, capsys):
        ui.hint("try this")
        out = capsys.readouterr().out
        assert "try this" in out

    def test_step_with_number(self, capsys):
        ui.step(1, "Building")
        out = capsys.readouterr().out
        assert "[1]" in out
        assert "Building" in out

    def test_step_without_number(self, capsys):
        ui.step(None, "Compiling")
        out = capsys.readouterr().out
        assert "Compiling" in out


class TestBanner:
    def test_banner_with_version(self, capsys):
        ui.banner("Build complete", version="1.0.0")
        out = capsys.readouterr().out
        assert "Build complete" in out or "smart-apple-dev" in out


class TestSummary:
    def test_summary_renders_rows(self, capsys):
        ui.summary([("Build", "ok"), ("Duration", "1.2s")])
        out = capsys.readouterr().out
        assert "Build" in out
        assert "ok" in out
        assert "Duration" in out
        assert "1.2s" in out

    def test_empty_summary(self, capsys):
        ui.summary([])  # should not raise
        out = capsys.readouterr().out
        assert out == ""


class TestSpinner:
    def test_spinner_runs_block(self, capsys):
        with ui.spinner("test"):
            time.sleep(0.01)
        out = capsys.readouterr().out
        assert "test" in out

    def test_spinner_propagates_exception(self):
        with pytest.raises(ValueError):
            with ui.spinner("test"):
                raise ValueError("boom")


class TestPanel:
    def test_panel_renders(self, capsys):
        ui.panel("Title", "Body text")
        out = capsys.readouterr().out
        assert "Title" in out
        assert "Body text" in out


class TestTermWidth:
    def test_term_width_returns_int(self):
        w = ui.term_width()
        assert isinstance(w, int)
        assert w >= 40


class TestFallbackWithoutRich:
    """When rich is unavailable, ui should still produce output."""

    def test_no_rich_fallback(self, capsys, monkeypatch):
        # Force _get_console to return None by patching _CONSOLE_SINGLETON
        monkeypatch.setattr(ui, "_CONSOLE_SINGLETON", None)
        # Make _HAS_RICH False so _get_console returns None
        monkeypatch.setattr(ui, "_HAS_RICH", False)
        # banner prints "smart-apple-dev" by default; success/error/summary still work
        ui.banner("ignored title")
        ui.success("yes")
        ui.error("no")
        ui.summary([("k", "v")])
        out, err = capsys.readouterr()
        assert "smart-apple-dev" in out
        assert "yes" in out
        assert "no" in err
        assert "k" in out and "v" in out
