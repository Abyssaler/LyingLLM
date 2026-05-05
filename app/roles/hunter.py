from __future__ import annotations

from typing import Optional

from app.models.role import Faction, RoleConfig, SkillDefinition, SkillTargetType
from app.roles.base import BaseRole, ActionResult, GameContext


class Hunter(BaseRole):
    DEFAULT_CONFIG = RoleConfig(
        name="猎人",
        faction=Faction.VILLAGE,
        night_priority=None,
        description="死亡时可开枪带走一名玩家",
        skills=[
            SkillDefinition(
                name="shoot",
                phase="on_death",
                description="死亡时可选择开枪带走一名存活玩家",
                target_type=SkillTargetType.SINGLE_PLAYER,
                trigger="on_death",
                can_shoot_on_witch_kill=True,
            )
        ],
        prompt_hint="你是猎人，当你死亡时（被投票处决或被狼人杀死）可以选择开枪带走一名存活玩家。",
    )

    async def night_action(self, agent, context: GameContext) -> ActionResult:
        return ActionResult(
            success=False,
            action_type="none",
            message="猎人没有夜间技能",
        )

    async def on_death(self, agent, context: GameContext) -> Optional[ActionResult]:
        shoot_target = context.extra.get("hunter_shoot_target")
        can_shoot = True
        death_causes = context.extra.get("death_causes", [])
        rules = context.rules
        if "witch_poison" in death_causes:
            can_shoot = rules.get("hunter_can_shoot_on_witch_kill", True) if rules else True

        if not can_shoot:
            return ActionResult(
                success=False,
                action_type="shoot_blocked",
                message="猎人被毒杀，无法开枪",
            )

        return ActionResult(
            success=True,
            action_type="shoot",
            target_id=shoot_target,
            message=f"猎人开枪带走玩家{shoot_target}",
        )

    def get_day_prompt(self, context: GameContext) -> str:
        return f"你是猎人。{self.prompt_hint}"