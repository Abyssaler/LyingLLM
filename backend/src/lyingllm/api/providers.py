"""Provider catalog API."""

from __future__ import annotations

from fastapi import APIRouter

from lyingllm.config.providers import get_provider_catalog

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
async def list_providers() -> list[dict]:
    catalog = get_provider_catalog()
    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "adapter": p.adapter,
            "is_configured": p.is_configured,
            "models": [
                {
                    "id": m.id,
                    "display_name": m.display_name,
                    "capabilities": {
                        "structured_output": m.capabilities.structured_output,
                        "json_mode": m.capabilities.json_mode,
                        "tool_calling": m.capabilities.tool_calling,
                        "reasoning_summary": m.capabilities.reasoning_summary,
                        "reasoning_content": m.capabilities.reasoning_content,
                        "encrypted_reasoning": m.capabilities.encrypted_reasoning,
                        "reasoning_effort": m.capabilities.reasoning_effort,
                        "max_context_tokens": m.capabilities.max_context_tokens,
                    },
                    "defaults": {
                        "temperature": m.defaults.temperature,
                        "top_p": m.defaults.top_p,
                        "max_output_tokens": m.defaults.max_output_tokens,
                        "reasoning_effort": m.defaults.reasoning_effort,
                        "reasoning_capture": m.defaults.reasoning_capture,
                    },
                }
                for m in p.models
            ],
        }
        for p in catalog
    ]
