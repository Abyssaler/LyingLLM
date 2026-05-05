from __future__ import annotations

from app.models.role import Faction, RoleConfig
from app.roles.base import BaseRole, ActionResult, GameContext


class Villager(BaseRole):
    DEFAULT_CONFIG = RoleConfig(
        name="村民",
        faction=Faction.VILLAGE,
        night_priority=None,
        description="无特殊技能，依靠推理发言辨别狼人",
        skills=[],
        prompt_hint="你是村民，没有特殊技能，依靠白天的发言和推理来辨别狼人。",
    )

    async def night_action(self, agent, context: GameContext) -> ActionResult:
        return ActionResult(
            success=False,
            action_type="none",
            message="村民没有夜间技能",
        )

    def get_night_prompt(self, context: GameContext) -> str:
        return "你是村民，夜晚没有特殊行动，请等待天亮。"