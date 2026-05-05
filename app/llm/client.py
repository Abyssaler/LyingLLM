from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.message import ConversationManager


@dataclass
class LLMResponse:
    content: str = ""
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class LLMRequest:
    messages: list[dict[str, str]] = field(default_factory=list)
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    json_mode: bool = True
    stream: bool = False
    extra: dict[str, Any] = field(default_factory=dict)