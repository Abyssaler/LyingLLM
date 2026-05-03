from __future__ import annotations

from app.models.role import Faction, RoleConfig, SkillDefinition, SkillTargetType
from app.roles.base import BaseRole, ActionResult, GameContext


class Werewolf(BaseRole):
    DEFAULT_CONFIG = RoleConfig(
        name="狼人",
        faction=Faction.WOLF,
        night_priority=2,
        description="夜间选择一名玩家击杀，互相知道身份",
        skills=[
            SkillDefinition(
                name="kill",
                phase="night",
                description="每晚选择一名玩家击杀",
                target_type=SkillTargetType.SINGLE_PLAYER,
                faction_discuss=True,
            )
        ],
        prompt_hint="你是狼人，夜间与同伴协商选择击杀目标。白天需要伪装身份，引导好人阵营误投村民。",
    )

    async def night_action(self, agent, context: GameContext) -> ActionResult:
        return ActionResult(
            success=True,
            action_type="kill",
            target_id=context.extra.get("wolf_kill_target"),
            data={"faction": "wolf"},
            message=f"狼人选择击杀目标",
        )

    def get_night_prompt(self, context: GameContext) -> str:
        wolves = context.extra.get("wolf_partner_ids", [])
        partners_str = "、".join(f"玩家{pid}号" for pid in wolves) if wolves else ""
        base = f"你是狼人。{self.prompt_hint}"
        if partners_str:
            base += f"\n你的狼人同伴是：{partners_str}。"
        base += "\n请与同伴协商，选择一名今晚要击杀的玩家。"
        return base