"""LLM provider adapters.

Each adapter translates a uniform ``LLMRequest`` into a provider-native
call and returns a normalized ``LLMResponse``.
"""

from __future__ import annotations

import json
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
