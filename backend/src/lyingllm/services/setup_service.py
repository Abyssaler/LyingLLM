"""Setup validation service.

Validates a ``GameSetupConfig`` before a game is created.
"""

from __future__ import annotations

from lyingllm.domain.models.game import GameSetupConfig
from lyingllm.domain.models.setup import SetupValidationResult, SetupValidationIssue
from lyingllm.config.providers import get_provider_catalog, get_model_config


class SetupService:
    def validate(self, config: GameSetupConfig) -> SetupValidationResult:
        errors: list[SetupValidationIssue] = []
        warnings: list[SetupValidationIssue] = []

        if len(config.players) != 12:
            errors.append(
                SetupValidationIssue(
                    code="PLAYER_COUNT", message="Exactly 12 players required"
                )
            )

        catalog = get_provider_catalog()
        catalog_ids = {p.id for p in catalog}

        for ps in config.players:
            mc = ps.model_config
            if mc is None:
                errors.append(
                    SetupValidationIssue(
                        player_id=ps.player_id,
                        code="MISSING_MODEL_CONFIG",
                        message="Player has no model configuration",
                    )
                )
                continue

            if mc.provider_id not in catalog_ids:
                errors.append(
                    SetupValidationIssue(
                        player_id=ps.player_id,
                        provider_id=mc.provider_id,
                        code="UNKNOWN_PROVIDER",
                        message=f"Provider '{mc.provider_id}' not registered",
                    )
                )
                continue

            provider_cfg = next(p for p in catalog if p.id == mc.provider_id)
            if not provider_cfg.is_configured:
                errors.append(
                    SetupValidationIssue(
                        player_id=ps.player_id,
                        provider_id=mc.provider_id,
                        code="PROVIDER_NOT_CONFIGURED",
                        message=f"Provider '{mc.provider_id}' API key not set",
                    )
                )

            known_models = {m.id for m in provider_cfg.models}
            if mc.model_id not in known_models and provider_cfg.models:
                # If provider has explicit model list, warn on unknown model
                warnings.append(
                    SetupValidationIssue(
                        player_id=ps.player_id,
                        provider_id=mc.provider_id,
                        model_id=mc.model_id,
                        code="UNKNOWN_MODEL",
                        message=f"Model '{mc.model_id}' not in provider catalog",
                    )
                )

            # Reasoning capture capability check
            model_cfg = get_model_config(mc.provider_id, mc.model_id)
            if model_cfg and mc.reasoning.capture != "auto":
                caps = model_cfg.capabilities
                capture = mc.reasoning.capture
                if capture == "summary" and not caps.reasoning_summary:
                    warnings.append(
                        SetupValidationIssue(
                            player_id=ps.player_id,
                            provider_id=mc.provider_id,
                            model_id=mc.model_id,
                            code="REASONING_CAPTURE_UNSUPPORTED",
                            message=f"Model does not support reasoning capture '{capture}'",
                        )
                    )

        return SetupValidationResult(
            ok=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )


# singleton
_service: SetupService | None = None


def get_setup_service() -> SetupService:
    global _service
    if _service is None:
        _service = SetupService()
    return _service
