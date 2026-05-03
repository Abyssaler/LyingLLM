from __future__ import annotations

from typing import Optional

from app.models.role import Faction, RoleConfig, SkillDefinition, SkillTargetType
from app.roles.base import BaseRole, ActionResult, GameContext


class Guard(BaseRole):
    DEFAULT_CONFIG = RoleConfig(
        name="守卫",
        faction=Faction.VILLAGE,
        night_priority=1,
        description="每晚可选择守护一名玩家，被守护的玩家若被狼人袭击则不会死亡；不可连续两晚守护同一人",
        skills=[
            SkillDefinition(
                name="guard",
                phase="night",
                description="每晚守护一名玩家，使其免受狼人袭击",
                target_type=SkillTargetType.SINGLE_PLAYER,
                cannot_guard_same_twice=True,
                can_empty_guard=True,
            )
        ],
        prompt_hint="你是守卫，每晚可以选择守护一名玩家使其免受狼人袭击，但不能连续两晚守同一人。",
    )

    def __init__(self, config: RoleConfig) -> None:
        super().__init__(config)
        self.last_guard_target: Optional[int] = None

    async def night_action(self, agent, context: GameContext) -> ActionResult:
        target_id = context.extra.get("guard_target")

        rules = context.rules
        cannot_guard_same = rules.get("guard_cannot_guard_same_twice", True) if rules else True

        if cannot_guard_same and target_id is not None and target_id == self.last_guard_target:
            return ActionResult(
                success=False,
                action_type="guard",
                target_id=target_id,
                message=f"守卫不能连续两晚守护同一人（玩家{target_id}号）",
            )

        result = ActionResult(
            success=True,
            action_type="guard",
            target_id=target_id,
            message=f"守卫守护玩家{target_id}号" if target_id is not None else "守卫选择空守",
        )
        self.last_guard_target = target_id
        return result

    def get_night_prompt(self, context: GameContext) -> str:
        alive_ids = context.alive_player_ids
        targets_str = "、".join(str(pid) for pid in alive_ids)
        parts = [f"你是守卫。{self.prompt_hint}"]
        parts.append(f"\n当前存活玩家：{targets_str}")
        if self.last_guard_target is not None and self.last_guard_target in alive_ids:
            parts.append(f"\n注意：你上一晚守护了玩家{self.last_guard_target}号，不能连续守同一人。")
        else:
            parts.append("\n你上一晚未守护任何玩家（或上轮守护的玩家已出局），可以自由选择。")
        parts.append("\n请选择一名玩家守护，或选择空守（不守护任何人）。")
        return "".join(parts)