from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.config.loader import YAMLLoader
from app.rules.manager import RuleManager, RuleConfig
from app.models.role import RoleConfig, RolesFile

router = APIRouter(prefix="/api/configs", tags=["configs"])

_loader = YAMLLoader()
_rule_manager = RuleManager(_loader)


@router.get("/roles")
async def list_roles() -> dict[str, Any]:
    available = _loader.list_configs("roles")
    roles_data: dict[str, Any] = {}
    for name in available:
        data = _loader.load_roles(name)
        roles_data[name] = data
    return {"available": available, "roles": roles_data}


@router.get("/roles/{name}")
async def get_role_config(name: str) -> dict[str, Any]:
    try:
        data = _loader.load_roles(name)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role config '{name}' not found")


@router.get("/rules")
async def list_rules() -> dict[str, Any]:
    available = _loader.list_configs("rules")
    rules_data: dict[str, Any] = {}
    for name in available:
        data = _loader.load_rules(name)
        rules_data[name] = data
    return {"available": available, "rules": rules_data}


@router.get("/rules/{name}")
async def get_rule_config(name: str) -> dict[str, Any]:
    try:
        data = _loader.load_rules(name)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule config '{name}' not found")


@router.get("/models")
async def list_models() -> dict[str, Any]:
    try:
        data = _loader.load_models("providers")
        return data
    except FileNotFoundError:
        return {"providers": {}, "default_provider": None, "default_model": None}


class ValidateRequest(dict.__class__):
    pass


from pydantic import BaseModel


class ConfigValidateRequest(BaseModel):
    roles_config: str = "classic"
    rules_config: str = "classic"
    player_count: int = 9
    model_provider: str | None = None


class ConfigValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


@router.post("/validate", response_model=ConfigValidateResponse)
async def validate_config(request: ConfigValidateRequest) -> ConfigValidateResponse:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        roles_data = _loader.load_roles(request.roles_config)
        roles_file = RolesFile(**roles_data)
        if "werewolf" not in roles_file.roles:
            errors.append(f"Role config '{request.roles_config}' must include 'werewolf' role")
    except FileNotFoundError:
        errors.append(f"Role config '{request.roles_config}' not found")
    except Exception as e:
        errors.append(f"Invalid role config '{request.roles_config}': {e}")

    try:
        rules = _rule_manager.load(request.rules_config)
        total_min = sum(r.get("min", 0) for r in rules.roles.values())
        if request.player_count < total_min:
            errors.append(f"Player count {request.player_count} is less than minimum required ({total_min}) for rules '{request.rules_config}'")
        if not rules.validate_player_count(request.player_count):
            warnings.append(f"Player count {request.player_count} may not satisfy role requirements for rules '{request.rules_config}'")
    except FileNotFoundError:
        errors.append(f"Rule config '{request.rules_config}' not found")
    except Exception as e:
        errors.append(f"Invalid rule config '{request.rules_config}': {e}")

    if request.model_provider:
        try:
            models_data = _loader.load_models("providers")
            providers = models_data.get("providers", {})
            if request.model_provider not in providers:
                errors.append(f"Model provider '{request.model_provider}' not found in providers config")
        except FileNotFoundError:
            warnings.append("Models config not found, cannot validate provider")

    return ConfigValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )