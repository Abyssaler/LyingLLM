"""LLM provider adapters.

Each adapter translates a uniform ``LLMRequest`` into a provider-native
call and returns a normalized ``LLMResponse``.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderAdapter(Protocol):
    """Uniform interface for all LLM provider adapters."""

    async def generate(self, request: "LLMRequest") -> "LLMResponse": ...


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMRequest:
    provider_id: str
    model_id: str
    messages: list[LLMMessage]
    output_schema: dict[str, Any] = field(default_factory=dict)
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int = 2000
    timeout_seconds: int = 30


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ReasoningTrace:
    mode: str = "off"
    content: str | None = None
    token_count: int | None = None


@dataclass
class LLMResponse:
    text: str = ""
    parsed_json: dict[str, Any] | None = None
    reasoning_trace: ReasoningTrace | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_ref: str | None = None


class MockAdapter:
    """Stub adapter that returns deterministic default actions."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        # Inspect the last user message to guess which action is needed
        last = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        action = self._guess_action(last, request.output_schema)
        return LLMResponse(
            text=json.dumps(action),
            parsed_json=action,
            reasoning_trace=ReasoningTrace(
                mode="self_explanation",
                content="Mock adapter default reasoning.",
                token_count=12,
            ),
            usage=TokenUsage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
        )

    def _guess_action(self, text: str, schema: dict[str, Any]) -> dict[str, Any]:
        # Simple heuristic: look for keywords in the prompt
        lower = text.lower()
        if "guard" in lower:
            return {"action": "guard", "target": None}
        if "wolf" in lower and "kill" in lower:
            return {"action": "wolf_vote_kill", "target": 1, "reason": "mock"}
        if "witch" in lower:
            return {"action": "witch", "use_save": False, "poison_target": None}
        if "seer" in lower or "预言家" in lower:
            return {"action": "seer", "target": 2}
        if "speech" in lower or "发言" in lower:
            return {"action": "speech", "content": "I am a villager. Trust me."}
        if "vote" in lower or "投票" in lower:
            return {"action": "vote", "target": "abstain"}
        if "hunter" in lower and "shoot" in lower:
            return {"action": "hunter_shoot", "target": None}
        if "sheriff" in lower and "transfer" in lower:
            return {"action": "sheriff_transfer", "target": "tear_badge"}
        if "self_destruct" in lower or "自爆" in lower:
            return {"action": "self_destruct", "target": None}
        # Fallback: return whatever the schema expects with minimal values
        return {"action": "speech", "content": ""}


class DeepSeekAdapter:
    """DeepSeek API adapter using aiohttp.

    Supports the new V4 ``deepseek-v4-flash`` / ``deepseek-v4-pro`` models
    where thinking mode is enabled by default and ``reasoning_content`` is
    returned alongside ``content``.

    See https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
    """

    THINKING_MODELS = {
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "deepseek-reasoner",
    }

    def __init__(self) -> None:
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.api_key_env = "DEEPSEEK_API_KEY"

    def _get_api_key(self) -> str:
        key = os.getenv(self.api_key_env, "")
        if not key:
            raise RuntimeError(f"Environment variable {self.api_key_env} is not set")
        return key

    async def generate(self, request: LLMRequest) -> LLMResponse:
        import aiohttp

        api_key = self._get_api_key()
        url = f"{self.base_url}/chat/completions"

        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]

        is_thinking_model = request.model_id in self.THINKING_MODELS
        # In thinking mode the model needs head-room for the chain of thought
        # plus the answer; bump the cap so JSON answers are not truncated.
        max_tokens = request.max_output_tokens
        if is_thinking_model and max_tokens < 4000:
            max_tokens = 4000

        payload: dict[str, Any] = {
            "model": request.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        # Thinking-mode models ignore temperature/top_p; for non-thinking
        # models we still want the user-supplied sampling controls.
        if not is_thinking_model:
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            if request.top_p is not None:
                payload["top_p"] = request.top_p

        # Explicitly enable thinking for V4 models so the API always returns
        # ``reasoning_content`` for the god-view to display.
        if request.model_id in {"deepseek-v4-flash", "deepseek-v4-pro"}:
            payload["thinking"] = {"type": "enabled"}

        # Request structured JSON output when a schema was supplied.
        if request.output_schema:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=request.timeout_seconds)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"DeepSeek API error {resp.status}: {text}")
                data = await resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content", "") or ""

        parsed_json = None
        if content:
            parsed_json = _parse_json_loose(content)

        reasoning_content = message.get("reasoning_content") or ""
        reasoning_trace = None
        if reasoning_content:
            reasoning_trace = ReasoningTrace(
                mode="full",
                content=reasoning_content,
                token_count=None,
            )

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return LLMResponse(
            text=content,
            parsed_json=parsed_json,
            reasoning_trace=reasoning_trace,
            usage=usage,
            raw_ref=json.dumps(data),
        )


def _parse_json_loose(content: str) -> dict[str, Any] | None:
    """Best-effort JSON parsing — tolerates fenced blocks and stray prose.

    The DeepSeek thinking model occasionally wraps JSON in markdown fences
    or prefixes it with a sentence, so we try a few strategies before
    giving up.
    """
    text = content.strip()
    # Strip markdown fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract the first {...} block via brace matching
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None
