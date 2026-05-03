from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.event_bus import EventBus, Event
from app.core.phase import Phase

router = APIRouter(tags=["websocket"])

GAME_EVENT_TYPE_MAP: dict[str, str] = {
    "game_start": "game_start",
    "game_end": "game_end",
    "game_paused": "game_paused",
    "game_resumed": "game_resumed",
    "game_aborted": "game_aborted",
    "phase_change": "phase_change",
    "state_snapshot": "state_snapshot",
    "sheriff_election": "sheriff_election",
    "sheriff_result": "sheriff_result",
    "night_begin": "night_begin",
    "wolf_discuss": "wolf_discuss",
    "night_action": "night_action",
    "dawn": "dawn",
    "speech": "speech",
    "last_words": "last_words",
    "vote": "vote",
    "vote_result": "vote_result",
    "tie_speech": "tie_speech",
    "tie_vote": "tie_vote",
    "execute": "execute",
    "on_death_skill": "on_death_skill",
    "thinking": "thinking",
    "action_retry": "action_retry",
    "action_fallback": "action_fallback",
    "error": "error",
}


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if game_id not in self._connections:
            self._connections[game_id] = []
        self._connections[game_id].append(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        if game_id in self._connections:
            self._connections[game_id] = [
                ws for ws in self._connections[game_id] if ws != websocket
            ]
            if not self._connections[game_id]:
                del self._connections[game_id]

    async def broadcast(self, game_id: str, data: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        connections = self._connections.get(game_id, [])
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.append(websocket)
        for ws in disconnected:
            self.disconnect(game_id, ws)

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass


manager = ConnectionManager()


def _event_to_ws_message(event: Event) -> dict[str, Any]:
    event_type = GAME_EVENT_TYPE_MAP.get(event.event_type, event.event_type)
    message: dict[str, Any] = {
        "event_type": event_type,
        "event_id": event.event_id,
        "round": event.round,
        "data": event.data,
    }
    if event.phase is not None:
        message["phase"] = event.phase.value if isinstance(event.phase, Phase) else event.phase
    return message


def _format_log_event(event_data: dict[str, Any], event_id: int) -> dict[str, Any]:
    event_type = GAME_EVENT_TYPE_MAP.get(event_data.get("event_type", ""), event_data.get("event_type", ""))
    message: dict[str, Any] = {
        "event_type": event_type,
        "event_id": str(event_id),
        "game_id": event_data.get("game_id", ""),
        "round": event_data.get("round", 0),
        "phase": event_data.get("phase", ""),
        "data": event_data.get("data", {}),
    }
    if "player_id" in event_data and event_data["player_id"] is not None:
        message["player_id"] = event_data["player_id"]
    return message


async def event_bus_handler(event: Event) -> None:
    if not event.data:
        return
    game_id = event.data.get("game_id", "")
    if not game_id:
        return
    message = _event_to_ws_message(event)
    await manager.broadcast(game_id, message)


def create_event_bus_with_ws(game_id: str) -> EventBus:
    bus = EventBus()

    async def ws_handler(event: Event) -> None:
        event_data = dict(event.data)
        event_data["game_id"] = game_id
        event_copy = Event(
            event_type=event.event_type,
            data=event_data,
            phase=event.phase,
            round=event.round,
            event_id=event.event_id,
        )
        message = _event_to_ws_message(event_copy)
        await manager.broadcast(game_id, message)

    bus.subscribe("phase_change", ws_handler)
    bus.subscribe("game_start", ws_handler)
    bus.subscribe("game_end", ws_handler)
    bus.subscribe("speech", ws_handler)
    bus.subscribe("vote", ws_handler)
    bus.subscribe("vote_result", ws_handler)
    bus.subscribe("thinking", ws_handler)
    bus.subscribe("last_words", ws_handler)
    bus.subscribe("execute", ws_handler)
    bus.subscribe("on_death_skill", ws_handler)
    bus.subscribe("dawn", ws_handler)
    bus.subscribe("night_action", ws_handler)
    bus.subscribe("wolf_discuss", ws_handler)
    return bus


@router.websocket("/ws/games/{game_id}")
async def websocket_game(
    websocket: WebSocket,
    game_id: str,
    last_event_id: int = Query(default=0),
) -> None:
    await manager.connect(game_id, websocket)
    from app.api.game import _games

    if last_event_id > 0 and game_id in _games:
        engine = _games[game_id]
        events = engine.log.get_events_after(last_event_id)
        for event in events:
            data = event.model_dump(mode="json")
            ws_msg = _format_log_event(data, event.event_id)
            try:
                await websocket.send_json(ws_msg)
            except Exception:
                break

        current_state = {
            "event_type": "state_snapshot",
            "event_id": "0",
            "game_id": game_id,
            "round": engine.state.round,
            "phase": engine.state.current_phase.value,
            "data": {
                "current_phase": engine.state.current_phase.value,
                "round": engine.state.round,
                "alive_players": [p.player_id for p in engine.game.get_alive_players()],
            },
        }
        try:
            await websocket.send_json(current_state)
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "subscribe":
                    await websocket.send_json({"type": "subscribed", "game_id": game_id})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
    except Exception:
        manager.disconnect(game_id, websocket)