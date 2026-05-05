from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status

from app.models.game import Game, GameConfig, GameCreateRequest
from app.core.engine import GameEngine
from app.core.phase import Phase
from app.core.state import InvalidTransitionError, PhaseMismatchError
from app.rules.manager import RuleManager
from app.config.loader import YAMLLoader
from app.api.ws import create_event_bus_with_ws

router = APIRouter(prefix="/api/games", tags=["games"])

_games: dict[str, GameEngine] = {}


def _get_engine(game_id: str) -> GameEngine:
    if game_id not in _games:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game {game_id} not found")
    return _games[game_id]


def _game_to_dict(game: Game, engine: GameEngine) -> dict[str, Any]:
    return {
        "game_id": game.game_id,
        "config": game.config.model_dump(),
        "current_phase": engine.state.current_phase.value,
        "round": engine.state.round,
        "players": [
            {
                "player_id": p.player_id,
                "name": p.name,
                "role": p.role,
                "faction": p.faction.value if p.faction else None,
                "status": p.status.value,
                "is_sheriff": p.is_sheriff,
                "is_alive": p.is_alive,
            }
            for p in game.players
        ],
        "sheriff_id": game.sheriff_id,
        "winner": game.winner,
        "mvp_player_id": game.mvp_player_id,
        "mvp_reason": game.mvp_reason,
        "created_at": game.created_at.isoformat() if game.created_at else None,
        "updated_at": game.updated_at.isoformat() if game.updated_at else None,
    }


def _win_check_after_night(engine: GameEngine) -> bool:
    current_round = engine.state.round
    for player in engine.game.players:
        if player.death_round != current_round or not player.death_cause:
            continue
        if any(cause in {"wolf_kill", "witch_poison"} for cause in player.death_cause):
            return True
    return False


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_game(request: GameCreateRequest) -> dict[str, Any]:
    config = GameConfig(
        player_count=request.player_count,
        roles_config=request.roles_config,
        rules_config=request.rules_config,
        enable_sheriff=request.enable_sheriff,
        enable_last_words=request.enable_last_words,
        role_assignments=request.role_assignments,
        player_models=request.player_models,
    )
    game = Game(config=config)
    loader = YAMLLoader()
    rule_manager = RuleManager(loader)
    rules = rule_manager.load(config.rules_config)
    event_bus = create_event_bus_with_ws(game.game_id)
    engine = GameEngine(game=game, rules_config=rules, event_bus=event_bus)
    engine.setup_game(
        player_count=config.player_count,
        role_assignments=config.role_assignments,
        player_models=config.player_models,
    )
    _games[game.game_id] = engine
    return _game_to_dict(game, engine)


@router.get("")
async def list_games() -> list[dict[str, Any]]:
    return [
        {"game_id": game_id, "current_phase": eng.state.current_phase.value, "round": eng.state.round,
         "player_count": len(eng.game.players), "winner": eng.game.winner,
         "created_at": eng.game.created_at.isoformat() if eng.game.created_at else None}
        for game_id, eng in _games.items()
    ]


@router.get("/{game_id}")
async def get_game(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    return _game_to_dict(engine.game, engine)


@router.post("/{game_id}/start")
async def start_game(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    try:
        phase = await engine.start_game()
        return {"game_id": game_id, "current_phase": phase.value, "round": engine.state.round}
    except (InvalidTransitionError, PhaseMismatchError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{game_id}/pause")
async def pause_game(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    try:
        phase = await engine.pause()
        return {"game_id": game_id, "current_phase": phase.value}
    except (InvalidTransitionError, PhaseMismatchError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{game_id}/resume")
async def resume_game(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    try:
        phase = await engine.resume()
        return {"game_id": game_id, "current_phase": phase.value}
    except (InvalidTransitionError, PhaseMismatchError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{game_id}/stop")
async def stop_game(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    phase = await engine.abort(reason="manual_stop")
    return {"game_id": game_id, "current_phase": phase.value}


class StepRequest(GameCreateRequest.__class__):
    pass


from pydantic import BaseModel


class StepPhaseRequest(BaseModel):
    phase: Optional[str] = None
    action: Optional[str] = None


class StepActionRequest(BaseModel):
    action_type: str
    player_id: Optional[int] = None
    target_id: Optional[int] = None
    data: Optional[dict[str, Any]] = None


class ActionSubmitRequest(BaseModel):
    player_id: int
    action_type: str
    target_id: Optional[int] = None
    data: Optional[dict[str, Any]] = None


@router.post("/{game_id}/step")
async def step_game(game_id: str, request: StepPhaseRequest = None) -> dict[str, Any]:
    engine = _get_engine(game_id)
    current = engine.state.current_phase

    try:
        if current == Phase.WAITING:
            phase = await engine.start_game()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.SHERIFF_ELECTION:
            phase = await engine.run_sheriff_election()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.NIGHT_BEGIN:
            result = await engine.run_night_phase()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": result.value,
                    "resolution": {"deaths": len(engine._pending_deaths) if engine._pending_deaths else 0}}

        if current == Phase.LAST_WORDS:
            dead_ids = engine._pending_deaths
            phase = await engine.run_last_words(dead_ids)
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.ON_DEATH_SKILL:
            phase = await engine.run_on_death_skill(engine._pending_deaths or [])
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.WIN_CHECK:
            after_night = _win_check_after_night(engine)
            result = await engine.run_win_check(after_night=after_night)
            return {"game_id": game_id, "from_phase": current.value, "to_phase": result.value,
                    "winner": engine.game.winner}

        if current == Phase.DISCUSS_ORDER:
            phase = engine.state.start_discuss()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.DISCUSS:
            await engine._run_discuss()
            phase = engine.state.finish_discuss()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.VOTE:
            await engine._run_vote()
            phase = engine.state.finish_vote()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.VOTE_RESULT:
            result = await engine._resolve_vote()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": result.value}

        if current == Phase.EXECUTE:
            eliminated = None
            return {"game_id": game_id, "from_phase": current.value, "to_phase": engine.state.current_phase.value}

        if current == Phase.TIE_SPEECH:
            engine.state.finish_tie_speech()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": engine.state.current_phase.value}

        if current == Phase.TIE_VOTE:
            engine.state.finish_tie_vote()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": engine.state.current_phase.value}

        if current == Phase.NO_ELIMINATION:
            phase = engine.state.finish_no_elimination()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.DAWN:
            resolution = engine._resolve_night()
            phase = await engine._process_dawn(resolution)
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.RETRY_OR_FALLBACK:
            phase = engine.state.finish_retry()
            return {"game_id": game_id, "from_phase": current.value, "to_phase": phase.value}

        if current == Phase.GAME_END:
            return {"game_id": game_id, "current_phase": "GAME_END",
                    "winner": engine.game.winner}

        if current == Phase.ABORTED:
            return {"game_id": game_id, "current_phase": "ABORTED"}

        if current == Phase.PAUSED:
            return {"game_id": game_id, "current_phase": "PAUSED", "detail": "Game is paused. Use /resume to continue."}

        return {"game_id": game_id, "current_phase": current.value, "detail": "No auto-step handler for this phase"}

    except (InvalidTransitionError, PhaseMismatchError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{game_id}/action")
async def submit_action(game_id: str, request: ActionSubmitRequest) -> dict[str, Any]:
    engine = _get_engine(game_id)
    return {
        "game_id": game_id,
        "player_id": request.player_id,
        "action_type": request.action_type,
        "target_id": request.target_id,
        "current_phase": engine.state.current_phase.value,
    }


@router.post("/{game_id}/rerun-action")
async def rerun_action(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    if engine.state.current_phase not in {
        Phase.WOLF_DISCUSS, Phase.NIGHT_ACTIONS, Phase.DISCUSS,
        Phase.VOTE, Phase.TIE_SPEECH, Phase.TIE_VOTE, Phase.ON_DEATH_SKILL,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot rerun in current phase")
    try:
        engine.state.enter_retry(reason="rerun_action")
        await engine._publish_phase(
            "RETRY_OR_FALLBACK",
            engine.state.retry_from.value if engine.state.retry_from else "unknown",
        )
        return {"game_id": game_id, "current_phase": engine.state.current_phase.value}
    except (InvalidTransitionError, PhaseMismatchError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{game_id}/mvp")
async def get_mvp(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    if engine.game.mvp_player_id is None:
        return {"game_id": game_id, "mvp": None, "detail": "MVP not yet determined"}
    return {
        "game_id": game_id,
        "mvp": {
            "player_id": engine.game.mvp_player_id,
            "reason": engine.game.mvp_reason,
        },
    }


@router.get("/{game_id}/log")
async def get_game_log(game_id: str) -> dict[str, Any]:
    engine = _get_engine(game_id)
    log = engine.log.build_log()
    return log.model_dump(mode="json")


@router.get("/{game_id}/log/day")
async def get_day_log(game_id: str) -> list[dict[str, Any]]:
    engine = _get_engine(game_id)
    log = engine.log.build_log()
    return [e.model_dump(mode="json") for e in log.day_log]


@router.get("/{game_id}/log/night")
async def get_night_log(game_id: str) -> list[dict[str, Any]]:
    engine = _get_engine(game_id)
    log = engine.log.build_log()
    return [e.model_dump(mode="json") for e in log.night_log]


@router.get("/{game_id}/events")
async def get_events(game_id: str, after_id: int = 0) -> list[dict[str, Any]]:
    engine = _get_engine(game_id)
    events = engine.log.get_events_after(after_id)
    return [e.model_dump(mode="json") for e in events]


@router.get("/{game_id}/thinking/{player_id}")
async def get_thinking(game_id: str, player_id: int) -> dict[str, Any]:
    engine = _get_engine(game_id)
    observer_log = engine.log._observer_log
    thinking_events = [
        e for e in observer_log
        if e.event_type == "thinking" and e.player_id == player_id
    ]
    return {
        "game_id": game_id,
        "player_id": player_id,
        "thinking_events": [e.model_dump(mode="json") for e in thinking_events],
    }
