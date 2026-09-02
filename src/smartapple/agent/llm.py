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
from pathlib import Path
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
# OpenAI-compatible providers (LM Studio, Custom, Groq, etc.)
# ============================================================
# Most modern LLM APIs follow the OpenAI /v1/chat/completions schema.
# Instead of duplicating code, we have a base class that all of them share.

class OpenAICompatibleProvider(LLMProvider):
    """Base for any OpenAI-compatible chat-completions endpoint."""

    name: str = "openai-compatible"
    default_model: str = ""
    default_base_url: str = ""
    api_key_env: str | None = None
    requires_api_key: bool = True
    env_var_overrides: dict[str, str] = {}

    def __init__(self, model=None, api_key=None, base_url=None, **kwargs):
        super().__init__(model=model, api_key=api_key, base_url=base_url, **kwargs)
        if not self.api_key and self.api_key_env:
            self.api_key = os.environ.get(self.api_key_env)
        if not self.base_url:
            env_var = self.env_var_overrides.get(self.name)
            self.base_url = (os.environ.get(env_var) if env_var else None) or self.default_base_url
        if not self.model:
            self.model = self.default_model

    def is_available(self):
        if self.requires_api_key and not self.api_key:
            return False, f"API key not set (env: {self.api_key_env})"
        if not self.base_url:
            return False, "base_url not configured"
        try:
            models = self.list_models()
            if models and self.model and not any(self.model in m for m in models):
                return True, f"{self.name}:{self.model} (model not in {len(models)} available)"
            return True, f"{self.name}:{self.model or '(default)'} ({len(models)} models)"
        except Exception as e:
            return True, f"{self.name}:{self.model} (connectivity: {e})"

    def list_models(self):
        if not self.base_url:
            return []
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            req = urllib.request.Request(
                f"{self.base_url.rstrip('/')}/v1/models",
                headers=headers,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return [m.get("id", m.get("name", "")) for m in data.get("data", []) if m.get("id") or m.get("name")]
        except Exception:
            return []

    def chat(self, messages, tools=None, stream=False):
        if self.requires_api_key and not self.api_key:
            raise RuntimeError(f"{self.name}: API key not set (env: {self.api_key_env})")
        if not self.base_url:
            raise RuntimeError(f"{self.name}: base_url not configured")

        body = {"model": self.model, "messages": [m.to_dict() for m in messages]}
        if tools:
            body["tools"] = tools

        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else ""
            raise RuntimeError(f"{self.name} API error {e.code}: {err_body[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"{self.name} network error: {e}")

        if "choices" not in data or not data["choices"]:
            raise RuntimeError(f"{self.name}: empty response: {json.dumps(data)[:200]}")
        choice = data["choices"][0]
        msg = choice.get("message", {})
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


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio local LLM server (no API key needed).

    LM Studio runs an OpenAI-compatible API on http://localhost:1234 by default.
    Override with LMSTUDIO_URL env var.
    """
    name = "lmstudio"
    default_model = "local-model"
    default_base_url = "http://localhost:1234"
    api_key_env = None
    requires_api_key = False
    env_var_overrides = {"lmstudio": "LMSTUDIO_URL"}


class CustomProvider(OpenAICompatibleProvider):
    """A custom OpenAI-compatible endpoint.

    Configure via env vars:
      SMART_APPLE_CUSTOM_BASE_URL  - the API base (required)
      SMART_APPLE_CUSTOM_API_KEY   - the API key (if needed)
    Or pass --base-url and --api-key to the agent.
    """
    name = "custom"
    default_model = "gpt-3.5-turbo"
    default_base_url = ""
    api_key_env = "SMART_APPLE_CUSTOM_API_KEY"
    requires_api_key = False
    env_var_overrides = {"custom": "SMART_APPLE_CUSTOM_BASE_URL"}


class GroqProvider(OpenAICompatibleProvider):
    """Groq Cloud (https://console.groq.com/). OpenAI-compatible, very fast."""
    name = "groq"
    default_model = "llama-3.1-70b-versatile"
    default_base_url = "https://api.groq.com/openai"
    api_key_env = "GROQ_API_KEY"
    requires_api_key = True


class MistralProvider(OpenAICompatibleProvider):
    """Mistral AI (https://console.mistral.ai/). OpenAI-compatible."""
    name = "mistral"
    default_model = "mistral-small-latest"
    default_base_url = "https://api.mistral.ai"
    api_key_env = "MISTRAL_API_KEY"
    requires_api_key = True


class TogetherProvider(OpenAICompatibleProvider):
    """Together AI (https://api.together.xyz/). OpenAI-compatible."""
    name = "together"
    default_model = "meta-llama/Llama-3-70b-chat-hf"
    default_base_url = "https://api.together.xyz"
    api_key_env = "TOGETHER_API_KEY"
    requires_api_key = True


class XAIProvider(OpenAICompatibleProvider):
    """xAI Grok (https://console.x.ai/). OpenAI-compatible."""
    name = "xai"
    default_model = "grok-2-latest"
    default_base_url = "https://api.x.ai"
    api_key_env = "XAI_API_KEY"
    requires_api_key = True


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek (https://platform.deepseek.com/). OpenAI-compatible."""
    name = "deepseek"
    default_model = "deepseek-chat"
    default_base_url = "https://api.deepseek.com"
    api_key_env = "DEEPSEEK_API_KEY"
    requires_api_key = True


class PerplexityProvider(OpenAICompatibleProvider):
    """Perplexity AI (https://docs.perplexity.ai/). OpenAI-compatible with search."""
    name = "perplexity"
    default_model = "llama-3.1-sonar-large-128k-online"
    default_base_url = "https://api.perplexity.ai"
    api_key_env = "PERPLEXITY_API_KEY"
    requires_api_key = True


# ============================================================
# Specialized providers (non-OpenAI APIs)
# ============================================================

class GitHubCopilotProvider(OpenAICompatibleProvider):
    """GitHub Copilot / GitHub Models API (https://github.com/marketplace/models).

    OpenAI-compatible. Auth via GitHub PAT or Copilot subscription token.
    Set GITHUB_TOKEN (or COPILOT_TOKEN). Base URL configurable via GITHUB_COPILOT_URL.
    """
    name = "copilot"
    default_model = "gpt-4o"
    default_base_url = "https://api.githubcopilot.com"
    api_key_env = "GITHUB_TOKEN"
    requires_api_key = True
    env_var_overrides = {"copilot": "GITHUB_COPILOT_URL"}


class GeminiProvider(OpenAICompatibleProvider):
    """Google Gemini (https://aistudio.google.com/).

    OpenAI-compatible via the generativelanguage.googleapis.com endpoint.
    Set GEMINI_API_KEY (or GOOGLE_API_KEY). Models: gemini-2.0-flash, gemini-1.5-pro, etc.
    Override base URL via GEMINI_BASE_URL.
    """
    name = "gemini"
    default_model = "gemini-2.0-flash"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    api_key_env = "GEMINI_API_KEY"
    requires_api_key = True
    env_var_overrides = {"gemini": "GEMINI_BASE_URL"}


class OpenCodeProvider(OpenAICompatibleProvider):
    """OpenCode.ai API (https://opencode.ai/).

    OpenAI-compatible. Set OPENCODE_API_KEY.
    Provides both g0 (general purpose) and zen (curated high-quality) model families.
    Override base URL via OPENCODE_BASE_URL.
    """
    name = "opencode"
    default_model = "gpt-4o"
    default_base_url = "https://api.opencode.ai"
    api_key_env = "OPENCODE_API_KEY"
    requires_api_key = True
    env_var_overrides = {"opencode": "OPENCODE_BASE_URL"}


class NousProvider(OpenAICompatibleProvider):
    """Nous Research (https://nousresearch.com/).

    OpenAI-compatible. Set NOUS_API_KEY.
    Models: Hermes series (hermes-3-llama-3.1-405b, nous-hermes-2-mistral, etc).
    """
    name = "nous"
    default_model = "hermes-3-llama-3.1-405b"
    default_base_url = "https://inference-api.nousresearch.com"
    api_key_env = "NOUS_API_KEY"
    requires_api_key = True


class SambaNovaProvider(OpenAICompatibleProvider):
    """SambaNova Cloud (https://cloud.sambanova.ai/).

    OpenAI-compatible. Set SAMBANOVA_API_KEY.
    Models: DeepSeek-V3.1, Llama-3.3-70B, Meta-Llama-3.1-405B, Qwen2.5-72B, etc.
    """
    name = "sambanova"
    default_model = "Meta-Llama-3.1-70B-Instruct"
    default_base_url = "https://api.sambanova.ai"
    api_key_env = "SAMBANOVA_API_KEY"
    requires_api_key = True


class ClineProvider(OpenAICompatibleProvider):
    """Cline (https://cline.bot/).

    OpenAI-compatible. Set CLINE_API_KEY. Routes to various underlying models.
    Override base URL via CLINE_BASE_URL.
    """
    name = "cline"
    default_model = "claude-3-5-sonnet"
    default_base_url = "https://api.cline.bot"
    api_key_env = "CLINE_API_KEY"
    requires_api_key = True
    env_var_overrides = {"cline": "CLINE_BASE_URL"}


class KiloProvider(OpenAICompatibleProvider):
    """Kilo Gateway (https://kilo.ai/).

    OpenAI-compatible AI gateway. Set KILO_API_KEY.
    Routes to many underlying models (OpenAI, Anthropic, Mistral, local, etc).
    """
    name = "kilo"
    default_model = "gpt-4o-mini"
    default_base_url = "https://api.kilo.ai"
    api_key_env = "KILO_API_KEY"
    requires_api_key = True
    env_var_overrides = {"kilo": "KILO_BASE_URL"}


class GatewayProvider(OpenAICompatibleProvider):
    """Generic OpenAI-compatible gateway.

    Set GATEWAY_API_KEY and GATEWAY_BASE_URL. Works with any OpenAI-compatible
    proxy (OpenRouter, Portkey, Cloudflare AI Gateway, LiteLLM, etc).
    """
    name = "gateway"
    default_model = "gpt-4o-mini"
    default_base_url = ""
    api_key_env = "GATEWAY_API_KEY"
    requires_api_key = True
    env_var_overrides = {"gateway": "GATEWAY_BASE_URL"}


class MiniMaxProvider(OpenAICompatibleProvider):
    """MiniMax (https://api.minimaxi.chat/).

    OpenAI-compatible. Set MINIMAX_API_KEY.
    Chinese-language optimized models. Also MiniMax-M3 etc.
    """
    name = "minimax"
    default_model = "MiniMax-Text-01"
    default_base_url = "https://api.minimaxi.chat"
    api_key_env = "MINIMAX_API_KEY"
    requires_api_key = True
    env_var_overrides = {"minimax": "MINIMAX_BASE_URL"}


# ============================================================
# Registry
# ============================================================

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "none": NoneProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "lmstudio": LMStudioProvider,
    "custom": CustomProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
    "together": TogetherProvider,
    "xai": XAIProvider,
    "deepseek": DeepSeekProvider,
    "perplexity": PerplexityProvider,
    # New providers
    "copilot": GitHubCopilotProvider,
    "gemini": GeminiProvider,
    "opencode": OpenCodeProvider,
    "nous": NousProvider,
    "sambanova": SambaNovaProvider,
    "cline": ClineProvider,
    "kilo": KiloProvider,
    "gateway": GatewayProvider,
    "minimax": MiniMaxProvider,
}


# Well-known models per provider (for --model auto-suggest and reference)
KNOWN_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "openai": [
        "gpt-4o", "gpt-4o-mini",
        "gpt-4-turbo", "gpt-4",
        "gpt-3.5-turbo", "o1-preview", "o1-mini",
    ],
    "ollama": [],       # populated dynamically from /api/tags
    "lmstudio": [],     # populated dynamically from /v1/models
    "custom": [],
    "groq": [
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "llama-3.2-90b-text-preview",
        "mixtral-8x7b-32768",
    ],
    "mistral": [
        "mistral-large-latest",
        "mistral-small-latest",
        "mistral-medium-latest",
        "codestral-latest",
    ],
    "together": [
        "meta-llama/Llama-3-70b-chat-hf",
        "meta-llama/Llama-3-8b-chat-hf",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
    ],
    "xai": ["grok-2-latest", "grok-2-mini", "grok-beta"],
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4-flash-vision-exp"],
    "perplexity": [
        "llama-3.1-sonar-large-128k-online",
        "llama-3.1-sonar-small-128k-online",
    ],
    # New providers
    "copilot": [
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
        "o1-preview", "o1-mini",
        "claude-3-5-sonnet", "claude-3-opus",
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.5-pro-exp",
        "gemini-exp-1206",
    ],
    "opencode": [
        "gpt-4o", "gpt-4o-mini",
        "claude-3-5-sonnet",
        "gpt-4-turbo",
    ],
    "nous": [
        "hermes-3-llama-3.1-405b",
        "hermes-2-mistral-7b",
        "nous-hermes-2-yi-34b",
        "phi-3-medium",
    ],
    "sambanova": [
        "Meta-Llama-3.1-70B-Instruct",
        "Meta-Llama-3.3-70B-Instruct",
        "Qwen2.5-72B-Instruct",
        "DeepSeek-V3.1",
    ],
    "cline": [
        "claude-3-5-sonnet",
        "claude-3-opus",
        "gpt-4o",
    ],
    "kilo": [
        "gpt-4o", "gpt-4o-mini",
        "claude-3-5-sonnet",
        "mistral-large",
        "local-model",
    ],
    "gateway": [],  # user-configured, populate via list_models_for()
    "minimax": [
        "MiniMax-Text-01",
        "abab6.5s-chat",
        "abab6-chat",
    ],
    "none": ["deterministic"],
}


# ============================================================
# Named instances (sub-providers / labels / variants)
# ============================================================
# Allows a single provider class to be reused with different configurations.
# Example syntax: "custom:venice" or "gateway:openrouter" or "ollama:workstation"
#
# Config persists at: ~/.smart-apple-dev/llm-providers.json
# Schema:
#   {
#     "instances": {
#       "custom:venice": {
#         "base_url": "https://api.venice.ai/v1",
#         "api_key": "${VENICE_API_KEY}",   # ${ENV_VAR} or literal
#         "default_model": "llama-3.3-70b",
#         "description": "Venice.ai - uncensored models",
#         "models": ["llama-3.3-70b", "qwen-2.5-72b"]
#       },
#       "gateway:openrouter": {
#         "base_url": "https://openrouter.ai/api/v1",
#         "api_key": "${OPENROUTER_API_KEY}",
#         "default_model": "anthropic/claude-3.5-sonnet"
#       }
#     }
#   }

_INSTANCE_CONFIG_PATH = Path.home() / ".smart-apple-dev" / "llm-providers.json"


# Built-in example instances that users can adopt with --provider-add
# These have known-good base URLs and default models.
EXAMPLE_INSTANCES = {
    # OpenRouter - routes to many models
    "custom:openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "${OPENROUTER_API_KEY}",
        "default_model": "anthropic/claude-3.5-sonnet",
        "description": "OpenRouter - routes to many models (Claude, GPT, Llama, etc)",
        "models": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.1-405b"],
    },
    # Portkey - AI gateway
    "custom:portkey": {
        "base_url": "https://api.portkey.ai/v1",
        "api_key": "${PORTKEY_API_KEY}",
        "default_model": "gpt-4o",
        "description": "Portkey AI gateway",
    },
    # Venice.ai - uncensored models
    "custom:venice": {
        "base_url": "https://api.venice.ai/v1",
        "api_key": "${VENICE_API_KEY}",
        "default_model": "llama-3.3-70b",
        "description": "Venice.ai - uncensored models",
        "models": ["llama-3.3-70b", "qwen-2.5-72b", "deepseek-coder-v2"],
    },
    # Cloudflare AI Gateway
    "custom:cloudflare": {
        "base_url": "https://gateway.ai.cloudflare.com/v1",
        "api_key": "${CLOUDFLARE_API_KEY}",
        "default_model": "@cf/meta/llama-3.1-70b-instruct",
        "description": "Cloudflare AI Gateway",
    },
    # LiteLLM proxy
    "custom:litellm": {
        "base_url": "http://localhost:4000",
        "api_key": "${LITELLM_API_KEY}",
        "default_model": "gpt-4o",
        "description": "LiteLLM local proxy",
    },
    # Second Copilot instance template
    "copilot:default": {
        "base_url": "https://api.githubcopilot.com",
        "api_key": "${GITHUB_TOKEN}",
        "default_model": "gpt-4o",
        "description": "Default Copilot (first one)",
    },
    "copilot:backup": {
        "base_url": "https://api.githubcopilot.com",
        "api_key": "${GITHUB_TOKEN_BACKUP}",
        "default_model": "claude-3-5-sonnet",
        "description": "Backup Copilot (alternative account/token)",
    },
}


def list_example_instances() -> dict[str, dict]:
    """Return the built-in example instances (read-only)."""
    return dict(EXAMPLE_INSTANCES)


def _load_instance_config() -> dict:
    """Load the persistent named-instance config."""
    if not _INSTANCE_CONFIG_PATH.exists():
        return {"instances": {}}
    try:
        with open(_INSTANCE_CONFIG_PATH) as f:
            data = json.load(f)
            if "instances" not in data:
                data["instances"] = {}
            return data
    except (json.JSONDecodeError, OSError):
        return {"instances": {}}


def _save_instance_config(data: dict) -> None:
    """Persist the named-instance config."""
    _INSTANCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_INSTANCE_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _resolve_env_ref(value: str) -> str:
    """Expand ${ENV_VAR} references in config strings."""
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, value)
    return value


def list_named_instances() -> dict[str, dict]:
    """Return all configured named instances, e.g. {"custom:venice": {...}}."""
    return _load_instance_config().get("instances", {})


def get_instance_config(name: str) -> dict | None:
    """Get the config for a named instance, e.g. 'custom:venice'."""
    return list_named_instances().get(name)


def set_instance_config(name: str, config: dict) -> None:
    """Add or update a named instance.

    Example:
        set_instance_config("custom:venice", {
            "base_url": "https://api.venice.ai/v1",
            "api_key": "${VENICE_API_KEY}",
            "default_model": "llama-3.3-70b",
            "description": "Venice.ai uncensored",
        })
    """
    data = _load_instance_config()
    data["instances"][name] = config
    _save_instance_config(data)


def delete_instance_config(name: str) -> bool:
    """Remove a named instance. Returns True if removed."""
    data = _load_instance_config()
    if name in data.get("instances", {}):
        del data["instances"][name]
        _save_instance_config(data)
        return True
    return False


def make_provider_from_instance(name: str) -> LLMProvider | None:
    """Construct a configured provider from a named instance like 'custom:venice'."""
    cfg = get_instance_config(name)
    if not cfg:
        return None
    if ":" not in name:
        return None
    base_name, instance_label = name.split(":", 1)
    cls = _PROVIDERS.get(base_name)
    if cls is None:
        return None
    # Build kwargs
    kwargs = {}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    if cfg.get("api_key"):
        kwargs["api_key"] = _resolve_env_ref(cfg["api_key"])
    if cfg.get("default_model"):
        kwargs["model"] = cfg["default_model"]
    # Track the instance label for display
    instance = cls(**kwargs)
    instance._instance_label = instance_label  # type: ignore[attr-defined]
    instance._instance_full_name = name  # type: ignore[attr-defined]
    return instance


def list_providers() -> list[str]:
    """Return the names of all registered providers, including named instances.

    Output:
      - Base providers: ["anthropic", "openai", "custom", ...]
      - Named instances: ["custom:venice", "gateway:openrouter", ...]
    """
    base = list(_PROVIDERS.keys())
    instances = list(list_named_instances().keys())
    return base + instances


def list_providers_grouped() -> dict[str, list[str]]:
    """Return providers grouped by base name.

    Example:
        {
            "custom": ["custom", "custom:venice", "custom:openrouter"],
            "gateway": ["gateway", "gateway:openrouter"],
            "anthropic": ["anthropic"],
        }
    """
    grouped: dict[str, list[str]] = {}
    for name in _PROVIDERS.keys():
        grouped.setdefault(name, []).append(name)
    for inst_name in list_named_instances().keys():
        if ":" in inst_name:
            base = inst_name.split(":", 1)[0]
            grouped.setdefault(base, []).append(inst_name)
    return grouped


def get_provider_class(name: str) -> type[LLMProvider] | None:
    """Look up a provider class by name. Strips ':instance' suffix for named instances."""
    base = name.split(":", 1)[0] if ":" in name else name
    return _PROVIDERS.get(base)


def get_provider(name: str, **kwargs) -> LLMProvider | None:
    """Get a configured provider by name. Supports 'name' or 'name:instance_label' syntax.

    For named instances (e.g. 'custom:venice'), reads config from
    ~/.smart-apple-dev/llm-providers.json and merges with passed kwargs.
    """
    if ":" in name:
        instance = make_provider_from_instance(name)
        if instance is not None:
            # Apply any additional kwargs
            for k, v in kwargs.items():
                if v is not None and hasattr(instance, k):
                    setattr(instance, k, v)
            return instance
    cls = _PROVIDERS.get(name)
    if cls is None:
        return None
    return cls(**kwargs)


def auto_select_provider() -> LLMProvider:
    """Try each base provider in order and return the first available one.

    Named instances (e.g. 'custom:venice', 'gateway:openrouter') are NOT
    auto-selected — they require explicit configuration and selection.

    Priority (free/local first):
      1. ollama, lmstudio   (local, no key)
      2. anthropic, openai, gemini, copilot  (cloud, best quality)
      3. groq, mistral, together, xai, deepseek, perplexity, etc.
      4. custom, gateway   (user-configured)
      5. none  (deterministic fallback for testing)
    """
    priority = [
        # Free / local first
        "ollama", "lmstudio",
        # Major clouds
        "anthropic", "openai", "gemini", "copilot",
        # OpenAI-compatible clouds
        "groq", "mistral", "together", "xai", "deepseek", "perplexity",
        "sambanova", "opencode", "nous", "cline", "kilo",
        # User-configured
        "minimax", "gateway", "custom", "none",
    ]
    for name in priority:
        if name not in _PROVIDERS:
            continue
        cls = _PROVIDERS[name]
        p = cls()
        ok, _ = p.is_available()
        if ok:
            return p
    return NoneProvider()


def list_models_for(provider_name: str, base_url: str | None = None) -> list[str]:
    """List available models for a provider.

    Supports named instances like 'custom:venice'. For those, uses the
    instance's configured base_url and models list (from config file).

    For local/OpenAI-compatible providers, this queries the API live.
    For cloud providers, returns the curated KNOWN_MODELS list.
    """
    # Handle named instances
    if ":" in provider_name:
        cfg = get_instance_config(provider_name)
        if cfg:
            # Return models from config, or try live query with instance base_url
            if cfg.get("models"):
                return cfg["models"]
            inst_base = cfg.get("base_url")
            # Try live query with instance's base_url
            try:
                inst = make_provider_from_instance(provider_name)
                if inst and hasattr(inst, "base_url"):
                    models = inst.list_models()
                    if models:
                        return models
            except Exception:
                pass
            return cfg.get("models", [])
        return []

    if provider_name not in _PROVIDERS:
        return []
    cls = _PROVIDERS[provider_name]

    if issubclass(cls, OpenAICompatibleProvider):
        try:
            instance = cls(base_url=base_url) if base_url else cls()
            models = instance.list_models()
            if models:
                return models
        except Exception:
            pass

    if issubclass(cls, OllamaProvider):
        try:
            instance = cls()
            req = urllib.request.Request(f"{instance.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass

    return KNOWN_MODELS.get(provider_name, [])
