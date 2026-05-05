from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
from uuid import uuid4

from app.core.phase import Phase


@dataclass
class Event:
    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    phase: Phase | None = None
    round: int = 0
    event_id: str = field(default_factory=lambda: uuid4().hex[:12])


EventHandler = Callable[[Event], Coroutine[Any, Any, None] | None]


class EventBus:
    def __init__(self) -> None:
        self._sync_subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._once_subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._sync_subscribers[event_type].append(handler)

    def subscribe_once(self, event_type: str, handler: EventHandler) -> None:
        self._once_subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        subs = self._sync_subscribers.get(event_type, [])
        if handler in subs:
            subs.remove(handler)
        once_subs = self._once_subscribers.get(event_type, [])
        if handler in once_subs:
            once_subs.remove(handler)

    async def publish(self, event_type: str, data: dict[str, Any] | None = None, **kwargs: Any) -> Event:
        event = Event(event_type=event_type, data=data or {}, **kwargs)
        self._history.append(event)

        handlers = list(self._sync_subscribers.get(event_type, []))
        once_handlers = list(self._once_subscribers.get(event_type, []))
        self._once_subscribers[event_type] = [
            h for h in self._once_subscribers.get(event_type, [])
            if h not in once_handlers
        ]

        for handler in handlers + once_handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result

        return event

    async def publish_phase_change(
        self,
        from_phase: Phase | str,
        to_phase: Phase | str,
        round: int,
        data: dict[str, Any] | None = None,
    ) -> Event:
        from_phase_value = from_phase.value if isinstance(from_phase, Phase) else str(from_phase)
        to_phase_value = to_phase.value if isinstance(to_phase, Phase) else str(to_phase)
        return await self.publish(
            event_type="phase_change",
            data={"from_phase": from_phase_value, "to_phase": to_phase_value, **(data or {})},
            phase=to_phase if isinstance(to_phase, Phase) else None,
            round=round,
        )

    async def publish_game_event(
        self, event_type: str, phase: Phase, round: int, data: dict[str, Any] | None = None,
        player_id: int | None = None,
    ) -> Event:
        event_data = data or {}
        if player_id is not None:
            event_data["player_id"] = player_id
        return await self.publish(
            event_type=event_type,
            data=event_data,
            phase=phase,
            round=round,
        )

    def get_history(self, after_id: str | None = None, event_type: str | None = None) -> list[Event]:
        events = self._history
        if after_id is not None:
            found = False
            filtered = []
            for e in events:
                if found:
                    filtered.append(e)
                if e.event_id == after_id:
                    found = True
            events = filtered
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        return events

    def clear_history(self) -> None:
        self._history.clear()

    def clear_all(self) -> None:
        self._sync_subscribers.clear()
        self._once_subscribers.clear()
        self._history.clear()
