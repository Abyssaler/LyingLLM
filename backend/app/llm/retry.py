from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.client import LLMRequest, LLMResponse
from app.llm.adapter import ProviderAdapter, create_adapter, AdapterConfig


@dataclass
class RetryPolicy:
    max_retries: int = 3
    retry_on_parse_error: bool = True
    retry_on_validation_error: bool = True
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True
    fallback_model: Optional[str] = None
    fallback_provider: Optional[str] = None
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0


class RetryExhaustedError(Exception):
    def __init__(self, message: str, attempts: int = 0, last_error: Optional[str] = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class RetryHandler:
    def __init__(self, policy: RetryPolicy) -> None:
        self.policy = policy

    def should_retry(self, error_type: str, attempt: int) -> bool:
        if attempt >= self.policy.max_retries:
            return False
        retry_map: dict[str, bool] = {
            "parse_error": self.policy.retry_on_parse_error,
            "validation_error": self.policy.retry_on_validation_error,
            "timeout": self.policy.retry_on_timeout,
            "rate_limit": self.policy.retry_on_rate_limit,
        }
        return retry_map.get(error_type, False)

    def get_delay(self, attempt: int) -> float:
        delay = self.policy.initial_delay * (self.policy.backoff_factor ** attempt)
        return min(delay, self.policy.max_delay)

    def has_fallback(self) -> bool:
        return self.policy.fallback_model is not None and self.policy.fallback_provider is not None

    def get_fallback_request(self, original_request: LLMRequest) -> LLMRequest:
        if not self.has_fallback():
            raise ValueError("No fallback model configured")
        return LLMRequest(
            messages=original_request.messages,
            model=self.policy.fallback_model or original_request.model,
            temperature=original_request.temperature,
            max_tokens=original_request.max_tokens,
            json_mode=original_request.json_mode,
            stream=original_request.stream,
            extra=original_request.extra,
        )