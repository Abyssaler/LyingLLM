"""WebSocket endpoint for real-time event streaming.

Uses a simple polling loop inside the WebSocket handler to avoid
cross-thread asyncio issues in TestClient.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lyingllm.services.game_service import get_game_service

router = APIRouter(prefix="/ws/games", tags=["websocket"])


@router.websocket("/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str, last_event_id: int = 0):
    svc = get_game_service()
    runner = svc.get(game_id)
    if runner is None:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    # Send missed events immediately
    last_sent = last_event_id
    for event in runner.events.after(last_sent):
        await _send_event(websocket, event)
        last_sent = event.event_id

    try:
        while True:
            await asyncio.sleep(0.5)
            for event in runner.events.after(last_sent):
                await _send_event(websocket, event)
                last_sent = event.event_id
    except WebSocketDisconnect:
        pass


async def _send_event(ws, event):
    await ws.send_json(
        {
            "event_id": event.event_id,
            "game_id": event.game_id,
            "round_no": event.round_no,
            "phase": event.phase.value,
            "event_type": event.event_type,
            "player_id": event.player_id,
            "visibility": event.visibility,
            "data": event.data,
            "timestamp": event.timestamp,
        }
    )
