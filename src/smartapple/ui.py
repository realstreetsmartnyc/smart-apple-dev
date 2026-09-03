"""Visual UI helpers for the smart-apple-dev CLI.

Thin wrapper over `rich` that:

* Detects whether the user is on a TTY and falls back to plain text
  (so CI logs, redirected output, and test capture stay readable).
* Provides a small vocabulary: ``banner``, ``step``, ``success``, ``error``,
  ``warning``, ``info``, ``hint``, ``summary`` — so every command
  looks the same.
* Renders the long Gradle/Mach-O invocations behind a spinner
  (``with spinner("Running gradlew assembleDebug"): ...``).
* Shows a coloured status table at the end of ``build`` / ``sign`` /
  ``install`` so the user sees *what happened* at a glance.

We deliberately keep this module dependency-light and side-effect-free
on import: if ``rich`` is missing, every call degrades to ``print``.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import time
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from typing import Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.text import Text

    _HAS_RICH = True
except Exception:  # pragma: no cover - rich is a hard dep, but stay safe
    _HAS_RICH = False


# ---------------------------------------------------------------------------
# Console singleton
# ---------------------------------------------------------------------------

# Force / disable colors:
#   SMART_APPLE_DEV_NO_COLOR=1   -> never color
#   SMART_APPLE_DEV_FORCE_COLOR=1 -> always color
# Defaults: color when stderr/stdout is a TTY.
def _want_color() -> bool:
    if os.environ.get("SMART_APPLE_DEV_NO_COLOR") == "1":
        return False
    if os.environ.get("SMART_APPLE_DEV_FORCE_COLOR") == "1":
        return True
    return sys.stdout.isatty() or os.environ.get("CI") == "true"


# Console singleton — recreated when sys.stdout changes.
# This handles the pytest/captured-streams case where sys.stdout is swapped
# after import; we want our output to follow the current sys.stdout.
def _current_stdout() -> Any:
    """Return the current sys.stdout, with a small allow-list for pytest."""
    return sys.stdout


def _get_console() -> Any:
    global _CONSOLE_SINGLETON, _CONSOLE_STDOUT_ID
    if not _HAS_RICH:
        return None
    out = _current_stdout()
    # Recreate the Console if sys.stdout was swapped (e.g. by pytest capsys)
    if _CONSOLE_SINGLETON is None or id(out) != _CONSOLE_STDOUT_ID:
        _CONSOLE_SINGLETON = Console(
            force_terminal=_want_color(),
            no_color=not _want_color(),
            highlight=False,
            soft_wrap=True,
            file=out,
        )
        _CONSOLE_STDOUT_ID = id(out)
    return _CONSOLE_SINGLETON


_CONSOLE_SINGLETON: Any = None
_CONSOLE_STDOUT_ID: int = 0


# Backwards-compatible attribute used throughout the module.
def _console() -> Any:
    return _get_console()


# Re-export an indicator so tests can detect fallback
USING_RICH = _HAS_RICH and _console() is not None


# ---------------------------------------------------------------------------
# Status glyphs
# ---------------------------------------------------------------------------

class Glyph:
    """Unicode glyphs that fall back to ASCII for very old terminals."""
    OK = "[OK]" if not _want_color() else "\u2705"        # [OK] / ✅
    FAIL = "[FAIL]" if not _want_color() else "\u274C"     # [FAIL] / ❌
    WARN = "[WARN]" if not _want_color() else "\u26A0\uFE0F"  # ⚠️
    INFO = "[INFO]" if not _want_color() else "\u2139\uFE0F"   # info
    HINT = "[HINT]" if not _want_color() else "\U0001F4A1"  # 💡
    ARROW = "->" if not _want_color() else "\u2192"        # ->
    BULLET = "*" if not _want_color() else "\u2022"        # •


# ---------------------------------------------------------------------------
# Banner / branding
# ---------------------------------------------------------------------------

BRAND_ASCII = r"""
   ____                       _                   _    ___           _
  / ___| _ __ ___   __ _ _ __| | _____  _ __   __| |  / _ \ _ __ ___| |__
  \___ \| '_ ` _ \ / _` | '__| |/ / _ \| '_ \ / _` | | | | | '__/ __| '_ \
   ___) | | | | | | (_| | |  |   < (_) | | | | (_| | | |_| | | | (__| | | |
  |____/|_| |_| |_|\__,_|_|  |_|\_\___/|_| |_|\__,_|  \___/|_|  \___|_| |_|
"""


def banner(title: str, subtitle: str | None = None, version: str | None = None) -> None:
    """Print a coloured brand banner.

    Falls back to a single line of text when rich isn't available.
    """
    line = "smart-apple-dev"
    if version:
        line += f" v{version}"
    if subtitle:
        line += f"  \u2014  {subtitle}"  # em-dash
    c = _console()
    if c is None:
        print(line)
        return
    text = Text(line, style="bold cyan")
    if title and title != line:
        text = Text(title, style="bold cyan")
    c.print(text)


# ---------------------------------------------------------------------------
# Step / status helpers
# ---------------------------------------------------------------------------

def step(n: int | None, label: str) -> None:
    """Print a numbered step: ``[1/3] Building...``"""
    if n is not None and n > 0:
        prefix = f"[{n}]"
    else:
        prefix = Glyph.BULLET
    c = _console()
    if c is None:
        print(f"{prefix} {label}")
        return
    style = "bold yellow" if (n is not None) else "cyan"
    c.print(f"[{style}]{prefix}[/{style}] {label}")


def info(label: str) -> None:
    c = _console()
    if c is None:
        print(f"{Glyph.INFO} {label}")
        return
    c.print("[cyan]" + Glyph.INFO + "[/cyan] " + str(label))


def success(label: str) -> None:
    c = _console()
    if c is None:
        print(f"{Glyph.OK} {label}")
        return
    c.print("[bold green]" + Glyph.OK + "[/bold green] " + str(label))


def warning(label: str) -> None:
    c = _console()
    if c is None:
        print(f"{Glyph.WARN} {label}")
        return
    c.print("[bold yellow]" + Glyph.WARN + "[/bold yellow] " + str(label))


def error(label: str) -> None:
    c = _console()
    if c is None:
        print(f"{Glyph.FAIL} {label}", file=sys.stderr)
        return
    # Rich's Console.stderr is True only at construction time. Build a tiny
    # stderr console on demand.
    err_console = _get_stderr_console()
    if err_console is None:
        # Captured stream was closed or rich's stderr Console can't init.
        # Fall back to a plain print to (current) sys.stderr.
        print(f"{Glyph.FAIL} {label}", file=sys.stderr)
        return
    err_console.print("[bold red]" + Glyph.FAIL + "[/bold red] " + str(label), style="red")


_STDERR_CONSOLE: Any = None
_STDERR_STDOUT_ID: int = 0


def _get_stderr_console() -> Any:
    global _STDERR_CONSOLE, _STDERR_STDOUT_ID
    if not _HAS_RICH:
        return None
    out = sys.stderr
    # Recreate if pytest swapped sys.stderr
    if _STDERR_CONSOLE is None or id(out) != _STDERR_STDOUT_ID:
        try:
            _STDERR_CONSOLE = Console(
                force_terminal=_want_color(),
                no_color=not _want_color(),
                highlight=False,
                soft_wrap=True,
                file=out,
                stderr=True,
            )
        except (ValueError, OSError):
            # Captured stream was closed; signal the caller to use print().
            return None
        _STDERR_STDOUT_ID = id(out)
    return _STDERR_CONSOLE


def hint(label: str) -> None:
    c = _console()
    if c is None:
        print(f"{Glyph.HINT} {label}")
        return
    c.print("[magenta]" + Glyph.HINT + "[/magenta] " + str(label))


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

@contextmanager
def spinner(label: str):
    """Context manager that shows a spinner while a long task runs.

    Degrades to plain ``print`` when rich isn't available or the output
    isn't a TTY (CI / redirected).
    """
    c = _console()
    show = c is not None and sys.stdout.isatty()
    if not show:
        info(label)
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            if elapsed > 0.5:
                info(f"  finished in {elapsed:.1f}s")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        TimeElapsedColumn(),
        console=c,
        transient=True,
    ) as progress:
        progress.add_task(description=label, total=None)
        try:
            yield
        except Exception:
            progress.stop()
            raise


# ---------------------------------------------------------------------------
# Summary panels
# ---------------------------------------------------------------------------

def summary(rows: Sequence[tuple[str, str]]) -> None:
    """Show a two-column summary at the end of a command.

    Example:
        ui.summary([
            ("Build",    "succeeded"),
            ("Provider", "local"),
            ("Artifact", "build/macos/hello.ipa"),
            ("Duration", "12.3s"),
        ])
    """
    if not rows:
        return
    c = _console()
    if c is None:
        for k, v in rows:
            print(f"  {k:<10}  {v}")
        return
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold", justify="right")
    table.add_column()
    for k, v in rows:
        table.add_row(k, str(v))
    c.print(table)


def panel(title: str, body: str | Iterable[str], style: str = "cyan") -> None:
    """Wrap a block of text in a coloured panel."""
    c = _console()
    if c is None:
        print(f"--- {title} ---")
        if isinstance(body, str):
            print(body)
        else:
            for line in body:
                print(line)
        print("---")
        return
    text = body if isinstance(body, str) else "\n".join(body)
    c.print(Panel(text, title=title, border_style=style))


# ---------------------------------------------------------------------------
# Width helper
# ---------------------------------------------------------------------------

def term_width(default: int = 80) -> int:
    """Return the current terminal width with a sensible fallback."""
    try:
        return max(40, shutil.get_terminal_size((default, 24)).columns)
    except (OSError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Buffered / no-color fallback for tests
# ---------------------------------------------------------------------------

class _BufferedConsole:
    """Tiny capture-friendly stand-in used by tests and CI logs."""

    def __init__(self) -> None:
        self.buf = io.StringIO()

    def print(self, *args: Any, **kwargs: Any) -> None:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        # Strip rich-style markup so tests can assert plain text.
        for a in args:
            s = str(a)
            # Remove simple [style]...[/style] markup
            import re
            s = re.sub(r"\[/?[a-z][a-z0-9_]*\]", "", s)
            self.buf.write(s + sep)
        self.buf.write(end)

    def text(self) -> str:
        return self.buf.getvalue()


# Re-export an indicator so tests can detect fallback
USING_RICH = _HAS_RICH
