from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.client import LLMRequest, LLMResponse


@dataclass
class AdapterConfig:
    provider: str
    adapter_type: str
    base_url: str
    api_key: str
    default_model: str
    max_tokens: int = 4096
    supports_streaming: bool = True
    supports_json_mode: bool = True


class ProviderAdapter(ABC):
    def __init__(self, config: AdapterConfig) -> None:
        self.config = config

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    def parse_response(self, raw_response: Any) -> dict[str, Any]:
        ...


class OpenAIAdapter(ProviderAdapter):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            import httpx

            model = request.model or self.config.default_model
            url = f"{self.config.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            payload: dict[str, Any] = {
                "model": model,
                "messages": request.messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            if request.json_mode and self.config.supports_json_mode:
                payload["response_format"] = {"type": "json_object"}

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                model=model,
                usage={"prompt_tokens": usage.get("prompt_tokens", 0),
                       "completion_tokens": usage.get("completion_tokens", 0),
                       "total_tokens": usage.get("total_tokens", 0)},
                raw=data,
                success=True,
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=request.model or self.config.default_model,
                success=False,
                error=str(e),
            )

    def parse_response(self, raw_response: Any) -> dict[str, Any]:
        if isinstance(raw_response, dict):
            choices = raw_response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                return {
                    "content": message.get("content", ""),
                    "role": message.get("role", ""),
                    "model": raw_response.get("model", ""),
                    "usage": raw_response.get("usage", {}),
                }
        return {"content": "", "role": "", "model": "", "usage": {}}


class ClaudeAdapter(ProviderAdapter):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            import httpx

            model = request.model or self.config.default_model
            url = f"{self.config.base_url.rstrip('/')}/v1/messages"
            headers = {
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            system_msg = ""
            user_messages: list[dict] = []
            for msg in request.messages:
                if msg["role"] == "system":
                    system_msg += msg["content"] + "\n"
                else:
                    user_messages.append({
                        "role": msg["role"] if msg["role"] != "assistant" else "assistant",
                        "content": msg["content"],
                    })

            payload: dict[str, Any] = {
                "model": model,
                "max_tokens": request.max_tokens,
                "messages": user_messages,
            }
            if system_msg:
                payload["system"] = system_msg.strip()

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            content_blocks = data.get("content", [])
            content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    content += block.get("text", "")

            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                model=model,
                usage={"prompt_tokens": usage.get("input_tokens", 0),
                       "completion_tokens": usage.get("output_tokens", 0),
                       "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)},
                raw=data,
                success=True,
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=request.model or self.config.default_model,
                success=False,
                error=str(e),
            )

    def parse_response(self, raw_response: Any) -> dict[str, Any]:
        if isinstance(raw_response, dict):
            content_blocks = raw_response.get("content", [])
            content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    content += block.get("text", "")
            return {
                "content": content,
                "role": "assistant",
                "model": raw_response.get("model", ""),
                "usage": raw_response.get("usage", {}),
            }
        return {"content": "", "role": "assistant", "model": "", "usage": {}}


ADAPTER_MAP: dict[str, type[ProviderAdapter]] = {
    "openai": OpenAIAdapter,
    "claude": ClaudeAdapter,
}


def create_adapter(config: AdapterConfig) -> ProviderAdapter:
    adapter_cls = ADAPTER_MAP.get(config.adapter_type)
    if adapter_cls is None:
        raise ValueError(f"Unknown adapter type: {config.adapter_type}. Available: {list(ADAPTER_MAP.keys())}")
    return adapter_cls(config)