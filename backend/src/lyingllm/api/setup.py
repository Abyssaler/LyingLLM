"""Setup validation API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from lyingllm.domain.models.game import GameSetupConfig, PlayerSetupConfig, RuntimeConfig
from lyingllm.domain.models.setup import ModelConfig, ReasoningConfig
from lyingllm.services.setup_service import get_setup_service
from lyingllm.api.games import (
    CreateGameRequest,
    _ModelConfigIn,
    _ReasoningConfigIn,
    _PlayerSetupIn,
    _RuntimeConfigIn,
)

router = APIRouter(prefix="/setup", tags=["setup"])


class ValidationResponse(BaseModel):
    ok: bool
    errors: list[dict]
    warnings: list[dict]


@router.post("/validate")
async def validate_setup(req: CreateGameRequest) -> ValidationResponse:
    svc = get_setup_service()

    def _to_mc(m: _ModelConfigIn | None) -> ModelConfig | None:
        if m is None:
            return None
        return ModelConfig(
            provider_id=m.provider_id,
            model_id=m.model_id,
            display_name=m.display_name,
            persona=m.persona,
            temperature=m.temperature,
            top_p=m.top_p,
            max_output_tokens=m.max_output_tokens,
            timeout_seconds=m.timeout_seconds,
            retry_limit=m.retry_limit,
            reasoning=ReasoningConfig(
                enabled=m.reasoning.enabled,
                effort=m.reasoning.effort,  # type: ignore[arg-type]
                capture=m.reasoning.capture,  # type: ignore[arg-type]
                show_to_observer=m.reasoning.show_to_observer,
                show_to_self=m.reasoning.show_to_self,
                persist_raw_response=m.reasoning.persist_raw_response,
            ),
        )

    players = [
        PlayerSetupConfig(
            player_id=p.player_id,
            display_name=p.display_name,
            model_config=_to_mc(p.cfg),
        )
        for p in req.players
    ]
    runtime = (
        RuntimeConfig(
            max_output_tokens=req.runtime.max_output_tokens,
            timeout_seconds=req.runtime.timeout_seconds,
            retry_limit=req.runtime.retry_limit,
        )
        if req.runtime
        else None
    )
    setup = GameSetupConfig(players=players, runtime=runtime)
    result = svc.validate(setup)
    return ValidationResponse(
        ok=result.ok,
        errors=[
            {
                "player_id": e.player_id,
                "provider_id": e.provider_id,
                "model_id": e.model_id,
                "code": e.code,
                "message": e.message,
            }
            for e in result.errors
        ],
        warnings=[
            {
                "player_id": w.player_id,
                "provider_id": w.provider_id,
                "model_id": w.model_id,
                "code": w.code,
                "message": w.message,
            }
            for w in result.warnings
        ],
    )
