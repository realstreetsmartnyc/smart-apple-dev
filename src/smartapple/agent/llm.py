"""LLM provider abstraction.

All providers share a common interface. The agent loop doesn't care which
provider it's using — it just calls chat() and gets messages back.

The "none" provider is a special case: it doesn't call an LLM at all,
but instead runs a deterministic plan. This is useful for:
- Testing the agent loop without API keys
- Users who don't want to send code to an LLM
- Offline operation
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator


# ============================================================
# Message types
# ============================================================

@dataclass
class Message:
    """A message in the conversation."""
    role: str  # "system", "user", "assistant", "tool"
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # for tool messages

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class ToolCall:
    """A request from the LLM to call a tool."""
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments),
            },
        }


@dataclass
class Completion:
    """Result of an LLM call."""
    message: Message
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    model: str = ""


# ============================================================
# Provider interface
# ============================================================

class LLMProvider(ABC):
    """Base class for LLM providers."""

    name: str = "abstract"
    default_model: str = ""
    requires_api_key: bool = True

    def __init__(self, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None, **kwargs):
        self.model = model or self.default_model
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs

    @abstractmethod
    def chat(self, messages: list[Message], tools: list[dict] | None = None,
             stream: bool = False) -> Completion:
        """Send a chat completion request."""
        ...

    def is_available(self) -> tuple[bool, str]:
        """Check if this provider is configured and reachable."""
        if self.requires_api_key and not self.api_key:
            return False, f"No API key for {self.name}"
        return True, "configured"


# ============================================================
# NoneProvider - deterministic, no LLM
# ============================================================

class NoneProvider(LLMProvider):
    """A deterministic provider that doesn't call any LLM.

    Useful for:
    - Testing the agent loop
    - Offline operation
    - Users who want predictable behavior

    It accepts a "plan" (a list of tool calls) and emits them one at a time.
    When the plan is exhausted, it returns a final message.
    """

    name = "none"
    default_model = "deterministic"
    requires_api_key = False

    def __init__(self, plan: list[dict] | None = None, **kwargs):
        super().__init__(**kwargs)
        # plan is a list of {"tool": "name", "args": {...}} or {"message": "..."}
        self.plan = plan or []
        self.plan_index = 0

    def is_available(self) -> tuple[bool, str]:
        return True, "always available (deterministic)"

    def chat(self, messages: list[Message], tools: list[dict] | None = None,
             stream: bool = False) -> Completion:
        if self.plan_index >= len(self.plan):
            # Done — return a final assistant message
            return Completion(
                message=Message(
                    role="assistant",
                    content="Plan complete. All requested steps were executed.",
                ),
                finish_reason="stop",
                model="none",
                usage={"input_tokens": 0, "output_tokens": 10},
            )

        step = self.plan[self.plan_index]
        self.plan_index += 1

        if "message" in step:
            return Completion(
                message=Message(role="assistant", content=step["message"]),
                finish_reason="stop",
                model="none",
            )

        if "tool" in step:
            return Completion(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(
                        id=f"call_{self.plan_index}",
                        name=step["tool"],
                        arguments=step.get("args", {}),
                    ).to_dict()],
                ),
                finish_reason="tool_calls",
                model="none",
            )

        # Unknown step type
        return Completion(
            message=Message(role="assistant", content=str(step)),
            finish_reason="stop",
            model="none",
        )


# ============================================================
# Anthropic provider
# ============================================================

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider (claude-3-5-sonnet, claude-3-haiku, etc)."""

    name = "anthropic"
    default_model = "claude-3-5-sonnet-20241022"
    requires_api_key = True

    def __init__(self, model: str | None = None, api_key: str | None = None, **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        if not self.api_key:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = self.base_url or "https://api.anthropic.com"

    def is_available(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "ANTHROPIC_API_KEY not set"
        return True, f"anthropic:{self.model}"

    def chat(self, messages: list[Message], tools: list[dict] | None = None,
             stream: bool = False) -> Completion:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        # Convert messages to Anthropic format
        system_prompt = ""
        chat_messages: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_prompt += m.content + "\n\n"
            elif m.role == "tool":
                chat_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }],
                })
            else:
                d = m.to_dict()
                if d.get("tool_calls"):
                    # Convert OpenAI-style tool_calls to Anthropic tool_use
                    content = []
                    for tc in d["tool_calls"]:
                        content.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"]),
                        })
                    chat_messages.append({"role": "assistant", "content": content})
                else:
                    chat_messages.append({"role": d["role"], "content": d["content"]})

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system_prompt:
            body["system"] = system_prompt.strip()
        if tools:
            # Convert OpenAI tools format to Anthropic tools format
            body["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]

        req = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else ""
            raise RuntimeError(f"Anthropic API error {e.code}: {err_body[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Anthropic network error: {e}")

        # Parse response
        content_text = ""
        tool_calls: list[dict] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block.get("input", {})),
                    },
                })

        usage = data.get("usage", {})
        return Completion(
            message=Message(
                role="assistant",
                content=content_text,
                tool_calls=tool_calls,
            ),
            finish_reason="tool_calls" if tool_calls else "stop",
            model=data.get("model", self.model),
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
        )


# ============================================================
# OpenAI provider
# ============================================================

class OpenAIProvider(LLMProvider):
    """OpenAI provider (gpt-4o, gpt-4-turbo, gpt-3.5-turbo, etc)."""

    name = "openai"
    default_model = "gpt-4o-mini"
    requires_api_key = True

    def __init__(self, model: str | None = None, api_key: str | None = None, **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        self.base_url = self.base_url or "https://api.openai.com"

    def is_available(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "OPENAI_API_KEY not set"
        return True, f"openai:{self.model}"

    def chat(self, messages: list[Message], tools: list[dict] | None = None,
             stream: bool = False) -> Completion:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        body: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
        }
        if tools:
            body["tools"] = tools

        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else ""
            raise RuntimeError(f"OpenAI API error {e.code}: {err_body[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenAI network error: {e}")

        choice = data["choices"][0]
        msg = choice["message"]
        return Completion(
            message=Message(
                role=msg.get("role", "assistant"),
                content=msg.get("content", "") or "",
                tool_calls=msg.get("tool_calls", []) or [],
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
        )


# ============================================================
# Ollama provider (local, no API key)
# ============================================================

class OllamaProvider(LLMProvider):
    """Ollama local LLM provider (no API key needed)."""

    name = "ollama"
    default_model = "llama3.2"
    requires_api_key = False

    def __init__(self, model: str | None = None, base_url: str | None = None, **kwargs):
        super().__init__(model=model, base_url=base_url, **kwargs)
        self.base_url = self.base_url or os.environ.get("OLLAMA_URL") or "http://localhost:11434"

    def is_available(self) -> tuple[bool, str]:
        # Check if Ollama is reachable
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            if not any(self.model in m for m in models):
                return False, f"Model {self.model} not found. Available: {models[:3]}"
            return True, f"ollama:{self.model}"
        except Exception as e:
            return False, f"Ollama not reachable at {self.base_url}: {e}"

    def chat(self, messages: list[Message], tools: list[dict] | None = None,
             stream: bool = False) -> Completion:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
        }
        if tools:
            body["tools"] = tools

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else ""
            raise RuntimeError(f"Ollama API error {e.code}: {err_body[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama network error: {e}")

        msg = data.get("message", {})
        return Completion(
            message=Message(
                role=msg.get("role", "assistant"),
                content=msg.get("content", "") or "",
                tool_calls=msg.get("tool_calls", []) or [],
            ),
            finish_reason="stop" if not msg.get("tool_calls") else "tool_calls",
            model=data.get("model", self.model),
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
        )


# ============================================================
# Registry
# ============================================================

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "none": NoneProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def list_providers() -> list[str]:
    return list(_PROVIDERS.keys())


def get_provider_class(name: str) -> type[LLMProvider] | None:
    return _PROVIDERS.get(name)


def auto_select_provider() -> LLMProvider:
    """Try each provider in order and return the first available one."""
    # Prefer NoneProvider for testing; in real use, prefer Ollama (free) > Anthropic > OpenAI
    for name in ["ollama", "anthropic", "openai", "none"]:
        cls = _PROVIDERS[name]
        p = cls()
        ok, _ = p.is_available()
        if ok:
            return p
    return NoneProvider()
