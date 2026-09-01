"""Agent loop: ReAct-style planning, tool execution, memory.

The loop:
1. Send the conversation to the LLM
2. If the LLM responds with text, print it (this is the agent's "thinking")
3. If the LLM responds with tool calls, execute them
4. Add the tool results to the conversation
5. Loop until the LLM stops calling tools (or hits a max iteration limit)

Conversation modes:
- "one-shot": agent "build my app" - runs to completion, prints final answer
- "repl": agent (no args) - interactive shell

Memory: per-project notes saved to ~/.smart-apple-dev/projects/<id>/memory.json
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .llm import (
    LLMProvider, Message, Completion, NoneProvider,
    auto_select_provider, list_providers, get_provider_class,
)
from .tools import (
    get_tools, get_tool, tool_schemas_for_llm,
)


SYSTEM_PROMPT = """You are smart-apple-dev, an agent that helps developers build, sign, install, and deploy iOS and macOS apps from Linux and Windows.

You have access to tools. Use them to:
- Build a project (build)
- Sign a built app (sign)
- Install to a device (install)
- Check the toolchain (doctor)
- Manage SDKs (sdk_list)
- Read and write files (read_file, write_file)
- Run shell commands (run_shell) - subject to a safety allowlist
- List available build providers (provider_list)
- Ask the user for clarification (ask_user) - use sparingly

When the user asks you to do something, plan the steps, then call the tools in order. After each tool call, observe the result and decide what to do next.

If a step fails, explain the error briefly and try a fix. If you can't fix it, report the issue to the user.

When you're done, summarize what you did. Be concise.

You are running on a non-Mac system (Linux or Windows). You CANNOT use any tool that requires macOS (like xcodebuild directly). The local provider uses clang + ldid + Apple SDKs to cross-compile, which works on Linux.

Available Apple SDKs come from the MacOSX-SDKs project (community mirror) for macOS targets, and from Mac Xcode (extracted via `smart-apple-dev sdk extract`) for iOS targets. Without an iOS SDK installed, you can only build for macos.
"""


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    max_iterations: int = 15
    max_tokens: int = 4096
    temperature: float = 0.0
    show_thinking: bool = True
    show_tool_results: bool = True
    project_dir: Path | None = None
    provider_name: str = "auto"  # "auto", "none", "anthropic", "openai", "ollama"
    model: str | None = None
    stream: bool = False
    memory_path: Path | None = None

    def to_dict(self) -> dict:
        return {
            "max_iterations": self.max_iterations,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "show_thinking": self.show_thinking,
            "show_tool_results": self.show_tool_results,
            "provider_name": self.provider_name,
            "model": self.model,
        }


@dataclass
class AgentResult:
    """Result of running the agent."""
    success: bool
    final_message: str
    iterations: int
    messages: list[Message] = field(default_factory=list)
    tool_calls_made: int = 0
    tokens_used: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "final_message": self.final_message,
            "iterations": self.iterations,
            "tool_calls_made": self.tool_calls_made,
            "tokens_used": self.tokens_used,
            "errors": self.errors,
        }


# ============================================================
# Memory
# ============================================================

def _project_id_for(project_dir: Path) -> str:
    """Get a stable project ID for memory storage."""
    import hashlib
    config_path = project_dir / "smartapple.toml"
    if config_path.exists():
        return hashlib.sha256(str(project_dir.resolve()).encode()).hexdigest()[:16]
    return "default"


def load_memory(memory_path: Path) -> dict:
    """Load project memory from disk."""
    if not memory_path.exists():
        return {"notes": [], "facts": {}, "last_updated": None}
    try:
        return json.loads(memory_path.read_text())
    except Exception:
        return {"notes": [], "facts": {}, "last_updated": None}


def save_memory(memory_path: Path, memory: dict) -> None:
    """Save project memory to disk."""
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory["last_updated"] = time.time()
    memory_path.write_text(json.dumps(memory, indent=2))


def add_memory_note(memory_path: Path, note: str) -> None:
    """Add a note to project memory."""
    memory = load_memory(memory_path)
    memory.setdefault("notes", []).append({
        "timestamp": time.time(),
        "text": note,
    })
    # Keep last 50 notes
    memory["notes"] = memory["notes"][-50:]
    save_memory(memory_path, memory)


# ============================================================
# The loop
# ============================================================

def _resolve_provider(config: AgentConfig) -> LLMProvider:
    if config.provider_name == "auto":
        return auto_select_provider()
    cls = get_provider_class(config.provider_name)
    if cls is None:
        raise ValueError(f"Unknown provider: {config.provider_name}. Available: {list_providers()}")
    if config.model:
        return cls(model=config.model)
    return cls()


def _print(text: str, prefix: str = "") -> None:
    if prefix:
        for line in text.split("\n"):
            print(f"{prefix} {line}")
    else:
        print(text)


def run_agent(
    user_request: str,
    config: AgentConfig | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> AgentResult:
    """Run the agent on a user request.

    Args:
        user_request: What the user wants done
        config: Agent configuration
        on_event: Optional callback for events ("thinking", "tool_call", "tool_result", "message", "done")

    Returns:
        AgentResult with success, final message, iteration count, etc.
    """
    config = config or AgentConfig()
    provider = _resolve_provider(config)
    tools = get_tools()
    schemas = tool_schemas_for_llm()

    available, reason = provider.is_available()
    if not available:
        return AgentResult(
            success=False,
            final_message=f"Provider {provider.name} not available: {reason}",
            iterations=0,
            errors=[reason],
        )

    # Memory
    project_dir = config.project_dir or Path.cwd()
    if config.memory_path:
        memory_path = config.memory_path
    else:
        from ..core.config import get_tool_dir
        project_id = _project_id_for(project_dir)
        memory_path = get_tool_dir() / "projects" / project_id / "memory.json"

    memory = load_memory(memory_path)

    # Build initial messages
    messages: list[Message] = [
        Message(role="system", content=SYSTEM_PROMPT),
    ]
    if memory.get("notes"):
        notes_text = "\n".join(f"- {n['text']}" for n in memory["notes"][-10:])
        messages.append(Message(
            role="system",
            content=f"Project memory (most recent):\n{notes_text}",
        ))
    messages.append(Message(role="user", content=user_request))

    def emit(event: str, data: dict) -> None:
        if on_event:
            on_event(event, data)

    iterations = 0
    tool_calls_made = 0
    tokens_used = 0
    errors: list[str] = []

    while iterations < config.max_iterations:
        iterations += 1

        # Call the LLM
        try:
            completion = provider.chat(messages, tools=schemas)
        except Exception as e:
            errors.append(f"LLM error: {e}")
            return AgentResult(
                success=False,
                final_message=f"LLM call failed: {e}",
                iterations=iterations,
                messages=messages,
                tool_calls_made=tool_calls_made,
                tokens_used=tokens_used,
                errors=errors,
            )

        msg = completion.message
        tokens_used += completion.usage.get("input_tokens", 0)
        tokens_used += completion.usage.get("output_tokens", 0)

        # Emit the assistant's text (if any)
        if msg.content:
            emit("message", {"content": msg.content})
            if config.show_thinking:
                _print(msg.content, prefix="[agent]")

        # If no tool calls, check if we're done (plan exhausted) or just a message step
        if not msg.tool_calls:
            # Check if provider is a NoneProvider and it's signaling completion
            if isinstance(provider, NoneProvider) and "Plan complete" in (msg.content or ""):
                emit("done", {"final_message": "Plan complete"})
                return AgentResult(
                    success=True,
                    final_message="Plan complete",
                    iterations=iterations,
                    messages=messages,
                    tool_calls_made=tool_calls_made,
                    tokens_used=tokens_used,
                )
            # Otherwise it's just an informational message from the LLM; continue the loop
            if config.show_thinking and msg.content:
                _print(msg.content, prefix="[agent]")
            continue

        # Add the assistant's tool-call message to history
        messages.append(msg)

        # Execute each tool call
        for tc in msg.tool_calls:
            tool_name = tc.get("function", {}).get("name")
            tool_args_str = tc.get("function", {}).get("arguments", "{}")
            tool_call_id = tc.get("id", f"call_{iterations}_{tool_calls_made}")

            try:
                tool_args = json.loads(tool_args_str) if tool_args_str else {}
            except json.JSONDecodeError:
                tool_args = {}

            tool = get_tool(tool_name)
            if tool is None:
                result_str = f"Error: Unknown tool {tool_name!r}"
            else:
                emit("tool_call", {"name": tool_name, "args": tool_args})
                if config.show_thinking:
                    args_preview = json.dumps(tool_args)
                    if len(args_preview) > 80:
                        args_preview = args_preview[:77] + "..."
                    _print(f"{tool_name}({args_preview})", prefix="[tool]")

                try:
                    result_str = tool.handler(tool_args)
                except Exception as e:
                    result_str = f"Error: {e}"

            tool_calls_made += 1
            emit("tool_result", {"name": tool_name, "result": result_str})
            if config.show_tool_results:
                _print(result_str, prefix="[result]")

            # Add tool result to history
            messages.append(Message(
                role="tool",
                content=result_str,
                tool_call_id=tool_call_id,
                name=tool_name,
            ))

            # Special handling: ask_user - the loop continues, LLM will get the answer
            if tool_name == "ask_user":
                # The tool handler returned a placeholder; in REPL mode, we'd ask the user.
                # For one-shot mode, we just note that we asked.
                if not config.show_thinking:
                    _print(f"Asked user: {tool_args.get('question', '')}", prefix="[ask]")

        # Loop continues - LLM will see the tool results

    # Hit max iterations
    errors.append(f"Hit max iterations ({config.max_iterations})")
    return AgentResult(
        success=False,
        final_message=f"Agent loop hit max iterations ({config.max_iterations})",
        iterations=iterations,
        messages=messages,
        tool_calls_made=tool_calls_made,
        tokens_used=tokens_used,
        errors=errors,
    )


def run_agent_with_provider_plan(
    plan: list[dict],
    config: AgentConfig | None = None,
) -> AgentResult:
    """Run the agent with a deterministic plan (for testing).

    The plan is a list of steps, each either:
    - {"message": "..."} - an assistant message
    - {"tool": "name", "args": {...}} - a tool call
    """
    config = config or AgentConfig()
    config.provider_name = "none"
    from .llm import NoneProvider
    config.provider_name = "none"
    return _run_with_none_provider(plan, config)


def _run_with_none_provider(plan: list[dict], config: AgentConfig) -> AgentResult:
    """Internal: run a plan through the loop using NoneProvider."""
    provider = NoneProvider(plan=plan)
    tools = get_tools()
    schemas = tool_schemas_for_llm()

    messages: list[Message] = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content="(test request - plan driven)"),
    ]

    iterations = 0
    tool_calls_made = 0
    tokens_used = 0
    plan_step = 0

    while iterations < config.max_iterations:
        iterations += 1

        completion = provider.chat(messages, tools=schemas)
        msg = completion.message
        tokens_used += completion.usage.get("input_tokens", 0)
        tokens_used += completion.usage.get("output_tokens", 0)

        if config.show_thinking and msg.content:
            _print(msg.content, prefix="[agent]")

        if not msg.tool_calls:
            return AgentResult(
                success=True,
                final_message=msg.content,
                iterations=iterations,
                messages=messages,
                tool_calls_made=tool_calls_made,
                tokens_used=tokens_used,
            )

        messages.append(msg)
        plan_step += 1

        for tc in msg.tool_calls:
            tool_name = tc.get("function", {}).get("name")
            tool_args_str = tc.get("function", {}).get("arguments", "{}")
            tool_call_id = tc.get("id", f"call_{iterations}_{tool_calls_made}")

            try:
                tool_args = json.loads(tool_args_str) if tool_args_str else {}
            except json.JSONDecodeError:
                tool_args = {}

            tool = get_tool(tool_name)
            if tool is None:
                result_str = f"Error: Unknown tool {tool_name!r}"
            else:
                if config.show_thinking:
                    args_preview = json.dumps(tool_args)
                    if len(args_preview) > 80:
                        args_preview = args_preview[:77] + "..."
                    _print(f"{tool_name}({args_preview})", prefix="[tool]")
                try:
                    result_str = tool.handler(tool_args)
                except Exception as e:
                    result_str = f"Error: {e}"

            tool_calls_made += 1
            if config.show_tool_results:
                _print(result_str, prefix="[result]")

            messages.append(Message(
                role="tool",
                content=result_str,
                tool_call_id=tool_call_id,
                name=tool_name,
            ))

    return AgentResult(
        success=False,
        final_message="Max iterations",
        iterations=iterations,
        messages=messages,
        tool_calls_made=tool_calls_made,
        tokens_used=tokens_used,
        errors=[f"Hit max iterations ({config.max_iterations})"],
    )
