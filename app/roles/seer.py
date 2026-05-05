from __future__ import annotations

from app.models.role import Faction, RoleConfig, SkillDefinition, SkillTargetType
from app.roles.base import BaseRole, ActionResult, GameContext


class Seer(BaseRole):
    DEFAULT_CONFIG = RoleConfig(
        name="预言家",
        faction=Faction.VILLAGE,
        night_priority=4,
        description="每晚可查验一名玩家的身份（是否为狼人）",
        skills=[
            SkillDefinition(
                name="check",
                phase="night",
                description="每晚查验一名玩家的身份",
                target_type=SkillTargetType.SINGLE_PLAYER,
                result_type="boolean_wolf",
            )
        ],
        prompt_hint="你是预言家，每晚可以查验一名玩家是否为狼人。利用查验结果带领好人阵营。",
    )

    async def night_action(self, agent, context: GameContext) -> ActionResult:
        target_id = context.extra.get("seer_check_target")
        return ActionResult(
            success=True,
            action_type="check",
            target_id=target_id,
            data={"result_type": "boolean_wolf"},
            message=f"预言家查验玩家{target_id}",
        )

    def get_night_prompt(self, context: GameContext) -> str:
        alive_ids = context.alive_player_ids
        possible_targets = [pid for pid in alive_ids if pid != context.extra.get("self_player_id")]
        targets_str = "、".join(str(pid) for pid in possible_targets)
        return (
            f"你是预言家。{self.prompt_hint}\n"
            f"当前存活可查验的玩家：{targets_str}\n"
            f"请选择一名玩家进行查验，你将得知其是否为狼人。"
        )