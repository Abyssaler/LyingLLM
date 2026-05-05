"""In-memory event log with JSONL persistence hooks.

MVP uses a single in-memory list; persistence can be added later.
"""

from __future__ import annotations

from lyingllm.domain.models.event import GameEvent
from lyingllm.domain.models.player import Faction


class EventLog:
    def __init__(self) -> None:
        self._events: list[GameEvent] = []
        self._next_id: int = 1

    def append(self, event: GameEvent) -> None:
        self._events.append(event)

    def next_id(self) -> int:
        eid = self._next_id
        self._next_id += 1
        return eid

    def all_events(self) -> list[GameEvent]:
        return list(self._events)

    def after(self, event_id: int) -> list[GameEvent]:
        return [e for e in self._events if e.event_id > event_id]

    def public_view(self) -> list[GameEvent]:
        return [e for e in self._events if "public" in e.visibility]

    def observer_view(self) -> list[GameEvent]:
        return list(self._events)

    def player_view(self, player_id: int, faction: Faction) -> list[GameEvent]:
        result: list[GameEvent] = []
        for e in self._events:
            if "public" in e.visibility:
                result.append(e)
                continue
            if f"player:{player_id}" in e.visibility:
                result.append(e)
                continue
            if "wolves" in e.visibility and faction == Faction.WOLF:
                result.append(e)
                continue
            # observer-only events are excluded for players
        return result

    def wolf_view(self) -> list[GameEvent]:
        return [
            e
            for e in self._events
            if "public" in e.visibility or "wolves" in e.visibility
        ]
