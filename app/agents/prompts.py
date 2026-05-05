from __future__ import annotations

from typing import Any, Optional

from app.agents.personality import Personality
from app.roles.base import BaseRole


CONSTRAINT_TEMPLATE = """\
【信息隔离约束】
1. 你只能使用你"应该"知道的信息，不能使用上帝视角或私有记忆中的信息来公开发言。
2. 你的思维过程(thinking)只对你自己和观赛者可见，不会进入公开发言。
3. 如果你是狼人阵营，你不能在公开场合透露你的狼人身份或同伴信息。
4. 如果你是好人阵营，你没有阵营共享记忆，不能互通私有信息。
5. 发言时必须保持角色一致，不能出现与角色身份矛盾的信息泄露。"""


class PromptBuilder:
    def __init__(self, rules_text: str = "") -> None:
        self.rules_text = rules_text

    def _build_rules_layer(self) -> str:
        if not self.rules_text:
            return ""
        return f"【规则层】\n{self.rules_text}"

    def _build_identity_layer(
        self,
        role: Optional[BaseRole],
        player_id: int,
        player_name: str,
        is_alive: bool,
        is_sheriff: bool,
    ) -> str:
        if role is None:
            return "【身份层】\n你的角色尚未分配。"
        lines = [
            "【身份层】",
            f"你是 玩家{player_id}号" + (f"（{player_name}）" if player_name else ""),
            f"角色：{role.name}",
            f"阵营：{role.faction.value}",
            f"状态：{'存活' if is_alive else '已出局'}",
        ]
        if is_sheriff:
            lines.append("特殊身份：警长（投票权重1.5票）")
        if role.prompt_hint:
            lines.append(role.prompt_hint)
        return "\n".join(lines)

    def _build_personality_layer(self, personality: Personality) -> str:
        text = personality.to_prompt_text()
        if not text or text == "你是一位普通的狼人杀玩家。":
            return ""
        return f"【人格层】\n{text}"

    def _build_memory_layer(self, memory_text: str) -> str:
        if not memory_text or memory_text == "暂无已知信息。":
            return ""
        return f"【记忆层】\n以下是你目前已知的信息：\n{memory_text}"

    def _build_constraint_layer(self, role: Optional[BaseRole]) -> str:
        return CONSTRAINT_TEMPLATE

    def build(
        self,
        role: Optional[BaseRole],
        personality: Personality,
        memory_text: str,
        phase_context: str,
        is_alive: bool = True,
        is_sheriff: bool = False,
        thinking_mode: bool = True,
        player_id: int = 0,
        player_name: str = "",
    ) -> str:
        parts: list[str] = []

        rules = self._build_rules_layer()
        if rules:
            parts.append(rules)

        identity = self._build_identity_layer(role, player_id, player_name, is_alive, is_sheriff)
        parts.append(identity)

        personality_text = self._build_personality_layer(personality)
        if personality_text:
            parts.append(personality_text)

        memory = self._build_memory_layer(memory_text)
        if memory:
            parts.append(memory)

        constraint = self._build_constraint_layer(role)
        parts.append(constraint)

        system_prompt = "\n\n".join(parts)

        if thinking_mode:
            system_prompt += (
                "\n\n【思考模式】\n"
                "请先进行内部推理（thinking字段），再给出公开行为（action/speech字段）。"
            )
            system_prompt += (
                '\n\n请以JSON格式回复：\n'
                '```json\n'
                '{\n'
                '  "thinking": "你的内心推理过程（不公开）",\n'
                '  "action": {"target": <目标玩家编号>, "type": "<动作类型>"},\n'
                '  "speech": "你的公开发言内容"\n'
                '}\n'
                '```'
            )
        else:
            system_prompt += (
                '\n\n请以JSON格式回复：\n'
                '```json\n'
                '{\n'
                '  "action": {"target": <目标玩家编号>, "type": "<动作类型>"},\n'
                '  "speech": "你的公开发言内容"\n'
                '}\n'
                '```'
            )

        return system_prompt

    def build_user_prompt(self, phase_context: str, extra_instructions: str = "") -> str:
        parts: list[str] = [f"【当前阶段指令】\n{phase_context}"]
        if extra_instructions:
            parts.append(f"【额外指令】\n{extra_instructions}")
        return "\n\n".join(parts)

    @staticmethod
    def build_on_death_prompt(
        role: BaseRole,
        player_id: int,
        is_sheriff: bool,
        alive_players: list[int],
        can_shoot: bool = True,
        can_transfer_sheriff: bool = False,
    ) -> str:
        lines = [
            "你已出局，现在需要做出死亡触发决策。",
            f"你的角色：{role.name}（玩家{player_id}号）",
        ]
        if can_shoot and role.has_on_death_skill():
            lines.append(f"你可以使用技能：{role.skills[0].description if role.skills else '开枪'}")
            lines.append(f"可选目标：{'、'.join(str(p) for p in alive_players)}")
        if can_transfer_sheriff and is_sheriff:
            lines.append("你是警长，需要选择一名存活玩家移交警徽。")
            lines.append(f"可选目标：{'、'.join(str(p) for p in alive_players)}")

        output_parts = ['"thinking": "你的内心推理"']
        if can_shoot and role.has_on_death_skill():
            output_parts.append('"death_skill": {"type": "shoot", "target": <玩家编号>}')
        if can_transfer_sheriff:
            output_parts.append('"sheriff_transfer": {"target": <玩家编号>}')
        output_parts.append('"last_words": "你的遗言"')

        lines.append(
            '\n请以JSON格式回复：\n```json\n{\n  '
            + ',\n  '.join(output_parts)
            + '\n}\n```'
        )
        return "\n".join(lines)