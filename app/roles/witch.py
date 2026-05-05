from __future__ import annotations

from typing import Any, Optional

from app.models.role import Faction, RoleConfig, SkillDefinition, SkillTargetType
from app.roles.base import BaseRole, ActionResult, GameContext


class Witch(BaseRole):
    DEFAULT_CONFIG = RoleConfig(
        name="女巫",
        faction=Faction.VILLAGE,
        night_priority=3,
        description="拥有一瓶解药（救人）和一瓶毒药（毒人），各限用一次",
        skills=[
            SkillDefinition(
                name="save",
                phase="night",
                description="解药：救活当晚被狼人杀害的玩家",
                target_type=SkillTargetType.WOLF_TARGET,
                uses=1,
                self_save_allowed=False,
            ),
            SkillDefinition(
                name="poison",
                phase="night",
                description="毒药：毒杀一名玩家",
                target_type=SkillTargetType.SINGLE_PLAYER,
                uses=1,
            ),
        ],
        prompt_hint="你是女巫，拥有一瓶解药和一瓶毒药，各限用一次。解药可救活当晚被狼刀的玩家，毒药可毒杀一名玩家。",
    )

    def __init__(self, config: RoleConfig) -> None:
        super().__init__(config)
        self.has_save_potion: bool = True
        self.has_poison_potion: bool = True

    async def night_action(self, agent, context: GameContext) -> ActionResult:
        actions: dict[str, Any] = {}
        wolf_target = context.wolf_kill_target

        if self.has_save_potion and wolf_target is not None:
            save_decision = context.extra.get("witch_save", False)
            if save_decision:
                actions["save_target"] = wolf_target
                self.has_save_potion = False

        poison_target = context.extra.get("witch_poison_target")
        if self.has_poison_potion and poison_target is not None:
            actions["poison_target"] = poison_target
            self.has_poison_potion = False

        return ActionResult(
            success=True,
            action_type="witch_action",
            data=actions,
            message="女巫使用技能",
        )

    def get_night_prompt(self, context: GameContext) -> str:
        wolf_target = context.wolf_kill_target
        parts = [f"你是女巫。{self.prompt_hint}"]
        if wolf_target is not None and self.has_save_potion:
            parts.append(f"\n今晚被狼人袭击的玩家是：玩家{wolf_target}号。你是否使用解药救活该玩家？")
            rules = context.rules
            can_self_save = rules.get("witch_can_self_save", False) if rules else False
            self_id = context.extra.get("self_player_id")
            if self_id is not None and wolf_target == self_id and not can_self_save:
                parts.append("（注意：规则规定女巫首夜不可自救）")
        elif not self.has_save_potion:
            parts.append("\n你的解药已经使用过了。")
        if self.has_poison_potion:
            alive_ids = context.alive_player_ids
            targets_str = "、".join(str(pid) for pid in alive_ids)
            parts.append(f"\n你可使用毒药毒杀一名玩家，可选目标：{targets_str}。也可以选择不使用。")
        else:
            parts.append("\n你的毒药已经使用过了。")
        return "".join(parts)
