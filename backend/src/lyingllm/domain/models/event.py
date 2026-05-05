"""Event and reasoning-trace models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lyingllm.domain.models.game import Phase


class GameEvent:
    """A single immutable entry in the unified event stream.

    Visibility tags control which derived views include the event:
    * ``public``     — visible to all
    * ``observer``   — visible to human spectators
    * ``player:{id}`` — visible to a specific player
    * ``wolves``     — visible to all wolf-faction players
    """

    def __init__(
        self,
        *,
        event_id: int,
        game_id: str,
        round_no: int,
        phase: Phase,
        event_type: str,
        player_id: int | None = None,
        visibility: list[str] | None = None,
        data: dict[str, Any] | None = None,
        raw_response_ref: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        self.event_id = event_id
        self.game_id = game_id
        self.round_no = round_no
        self.phase = phase
        self.event_type = event_type
        self.player_id = player_id
        self.visibility: list[str] = visibility or ["public"]
        self.data: dict[str, Any] = data or {}
        self.raw_response_ref = raw_response_ref
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()


class ReasoningTrace:
    """Normalized thinking / reasoning content from a provider."""

    def __init__(
        self,
        *,
        mode: str,  # off | hidden | summary | full | encrypted | usage_only | self_explanation
        provider: str,
        model: str,
        player_id: int,
        phase: Phase,
        action: str,
        content: str | None = None,
        token_count: int | None = None,
        encrypted_ref: str | None = None,
        raw_ref: str | None = None,
    ) -> None:
        self.mode = mode
        self.provider = provider
        self.model = model
        self.player_id = player_id
        self.phase = phase
        self.action = action
        self.content = content
        self.token_count = token_count
        self.encrypted_ref = encrypted_ref
        self.raw_ref = raw_ref
