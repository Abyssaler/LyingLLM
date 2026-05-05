"""Setup / configuration models shared between frontend and backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class ReasoningConfig:
    enabled: bool = False
    effort: (
        Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None
    ) = None
    capture: Literal["off", "summary", "full", "usage_only", "auto"] = "auto"
    show_to_observer: bool = True
    show_to_self: bool = True
    persist_raw_response: bool = True


@dataclass(slots=True)
class ModelConfig:
    provider_id: str
    model_id: str
    display_name: str | None = None
    persona: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int = 2000
    timeout_seconds: int = 30
    retry_limit: int = 2
    reasoning: ReasoningConfig = field(default_factory=ReasoningConfig)


@dataclass(slots=True)
class SetupValidationIssue:
    player_id: int | None = None
    provider_id: str | None = None
    model_id: str | None = None
    code: str = ""
    message: str = ""


@dataclass(slots=True)
class SetupValidationResult:
    ok: bool = False
    errors: list[SetupValidationIssue] = field(default_factory=list)
    warnings: list[SetupValidationIssue] = field(default_factory=list)
