"""Game lifecycle service.

Holds in-memory game runners and exposes high-level operations.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from lyingllm.domain.models.game import GameSetupConfig
from lyingllm.engine.runner import GameRunner
from lyingllm.storage.event_log import EventLog


class GameService:
    def __init__(self) -> None:
        self._games: dict[str, GameRunner] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._listeners: dict[str, list[Callable[[], None]]] = {}

    def create(self, game_id: str, setup: GameSetupConfig) -> GameRunner:
        runner = GameRunner(game_id=game_id, setup=setup)
        self._games[game_id] = runner
        self._listeners[game_id] = []
        return runner

    def get(self, game_id: str) -> GameRunner | None:
        return self._games.get(game_id)

    def list_ids(self) -> list[str]:
        return list(self._games.keys())

    def delete(self, game_id: str) -> None:
        self._games.pop(game_id, None)
        self._tasks.pop(game_id, None)
        self._listeners.pop(game_id, None)

    def subscribe(self, game_id: str, callback: Callable[[], None]) -> None:
        self._listeners.setdefault(game_id, []).append(callback)

    def unsubscribe(self, game_id: str, callback: Callable[[], None]) -> None:
        if game_id in self._listeners:
            try:
                self._listeners[game_id].remove(callback)
            except ValueError:
                pass

    def notify(self, game_id: str) -> None:
        for cb in self._listeners.get(game_id, []):
            try:
                cb()
            except Exception:
                pass

    async def run_game(self, game_id: str) -> None:
        runner = self._games.get(game_id)
        if runner is None:
            return
        while not runner.step():
            self.notify(game_id)
            await asyncio.sleep(0.01)  # tiny yield so WS can push
        self.notify(game_id)

    def start_game(self, game_id: str) -> None:
        task = asyncio.create_task(self.run_game(game_id))
        self._tasks[game_id] = task


# singleton
_service: GameService | None = None


def get_game_service() -> GameService:
    global _service
    if _service is None:
        _service = GameService()
    return _service
