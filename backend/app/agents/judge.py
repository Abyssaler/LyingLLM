from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.client import LLMRequest, LLMResponse
from app.llm.adapter import ProviderAdapter, AdapterConfig
from app.llm.retry import RetryHandler, RetryPolicy
from app.llm.message import ConversationManager


MVP_JUDGE_PROMPT_TEMPLATE = """你是本局狼人杀的裁判 AI，负责在游戏结束后评选 MVP。

## 本局游戏信息

胜方：{winner}
总轮数：{rounds}

## 完整对局日志

{game_log_text}

## 评选要求

1. 请在**胜利阵营**中评选 MVP，优先考虑存活玩家
2. 如果规则允许（mvp_include_dead_players={mvp_include_dead}），已淘汰玩家如有重大贡献也可评选
3. 评选维度参考：
   - 作为狼人时的伪装与欺骗效果
   - 作为好人时的推理与带票能力
   - 关键轮次的决策质量
   - 对团队胜利的贡献度

请以 JSON 格式回复：
```json
{{
  "mvp_player_id": <玩家编号>,
  "reason": "<评选理由>"
}}
```"""


@dataclass
class JudgeConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    personality: str = "strict"
    mvp_include_dead_players: bool = True


class JudgeAI:
    def __init__(
        self,
        config: JudgeConfig,
        adapter: ProviderAdapter,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.config = config
        self.adapter = adapter
        self.retry_handler = RetryHandler(retry_policy or RetryPolicy())
        self.conversation = ConversationManager()

    async def evaluate_mvp(
        self,
        winner: str,
        rounds: int,
        game_log_text: str,
        alive_player_ids: list[int],
        all_player_ids: list[int],
    ) -> dict[str, Any]:
        prompt = MVP_JUDGE_PROMPT_TEMPLATE.format(
            winner=winner,
            rounds=rounds,
            game_log_text=game_log_text,
            mvp_include_dead=self.config.mvp_include_dead_players,
        )
        self.conversation.clear_all()
        self.conversation.add_system(prompt)
        self.conversation.add_user("请根据以上信息评选本局 MVP，以 JSON 格式回复。")

        request = LLMRequest(
            messages=self.conversation.get_messages(),
            model=self.config.model,
            json_mode=True,
        )

        response = await self._call_with_retry(request)
        if not response.success:
            return {
                "mvp_player_id": None,
                "reason": f"MVP evaluation failed: {response.error}",
                "raw": response.content,
            }

        from app.agents.parser import OutputParser
        parser = OutputParser()
        try:
            parsed = parser.parse(response.content)
            mvp_id = parsed.action.get("mvp_player_id") if parsed.action else None
            reason = parsed.speech or parsed.thinking or ""
            if parsed.action:
                mvp_id = parsed.action.get("mvp_player_id") or parsed.action.get("target")
                reason = parsed.action.get("reason", reason)
            if mvp_id is None:
                for key, val in (parsed.action or {}).items():
                    if "mvp" in key.lower():
                        mvp_id = val
                    if "reason" in key.lower():
                        reason = val
            return {
                "mvp_player_id": mvp_id,
                "reason": reason,
                "raw": response.content,
            }
        except Exception as e:
            return {
                "mvp_player_id": None,
                "reason": f"MVP parse failed: {e}",
                "raw": response.content,
            }

    async def _call_with_retry(self, request: LLMRequest) -> LLMResponse:
        last_error: str = ""
        for attempt in range(self.retry_handler.policy.max_retries + 1):
            response = await self.adapter.complete(request)
            if response.success and response.content:
                return response
            last_error = response.error or "empty response"
            if not self.retry_handler.should_retry("parse_error", attempt):
                break
        return LLMResponse(
            content="",
            model=request.model or self.config.model,
            success=False,
            error=f"All retries exhausted: {last_error}",
        )