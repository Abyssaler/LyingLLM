"""Prompt builder for werewolf game agent actions.

Generates system prompts and user prompts for each action type,
embedding the current game state so the LLM can make informed decisions.
"""

from __future__ import annotations

import json
from typing import Any

from lyingllm.domain.models.player import Player, RoleId
from lyingllm.domain.models.game import GameState, NightActionSet, VoteState


_ROLE_DESCRIPTIONS: dict[RoleId, str] = {
    RoleId.SEER: "预言家 — 每晚可以查验一名玩家是好人还是狼人。",
    RoleId.WITCH: "女巫 — 拥有一瓶解药和一瓶毒药。解药可以救起当晚被狼人杀害的玩家，毒药可以毒杀一名玩家。每晚最多使用一瓶药。",
    RoleId.HUNTER: "猎人 — 被放逐或夜晚死亡时可以开枪带走一名玩家。",
    RoleId.GUARD: "守卫 — 每晚可以守护一名玩家，使其当晚不会被狼人杀害。不能连续两晚守护同一个人。",
    RoleId.VILLAGER: "村民 — 没有特殊技能，通过发言和投票帮助好人阵营找出狼人。",
    RoleId.WEREWOLF: "狼人 — 每晚与队友讨论并投票选择一名玩家杀害。白天要伪装成好人，隐藏身份。",
    RoleId.WHITE_WOLF_KING: "白狼王 — 属于狼人阵营。白天可以自爆并带走一名玩家。",
}


def _base_system_prompt(player: Player, state: GameState) -> str:
    """Base system prompt shared by all actions."""
    role_desc = _ROLE_DESCRIPTIONS.get(player.role, "")
    alive_ids = [p.id for p in state.players if p.alive]
    my_faction = player.faction.value

    wolves: list[int] = []
    if player.faction.value == "wolf":
        wolves = [
            p.id
            for p in state.players
            if p.alive and p.faction.value == "wolf" and p.id != player.id
        ]

    prompt = f"""你正在参与一局12人标准狼人杀游戏。你的座位号是 #{player.id}，身份是 {player.role.value}。

{role_desc}

当前游戏状态：
- 轮次：第 {state.round_no} 轮
- 存活玩家：{alive_ids}
- 你的阵营：{my_faction}
"""
    if wolves:
        prompt += f"- 你的狼队友：{wolves}\n"

    if player.role == RoleId.SEER:
        checked = sorted(player.checked_players)
        if checked:
            results = []
            for cid in checked:
                target = state.get_player(cid)
                if target:
                    camp = "狼人" if target.faction.value == "wolf" else "好人"
                    results.append(f"#{cid} → {camp}")
            prompt += f"- 你已查验过的玩家：{', '.join(results)}\n"

    if player.role == RoleId.WITCH:
        prompt += f"- 解药已使用：{'是' if player.witch_save_used else '否'}\n"
        prompt += f"- 毒药已使用：{'是' if player.witch_poison_used else '否'}\n"

    if player.role == RoleId.GUARD:
        prompt += f"- 上一晚守护对象：{player.last_guard_target if player.last_guard_target else '无'}\n"

    if state.sheriff_id:
        prompt += f"- 当前警长：玩家 #{state.sheriff_id}\n"

    return prompt


def _json_hint(schema: dict[str, Any]) -> str:
    return (
        "\n你必须以 JSON 格式回复，仅输出 JSON 对象，不要包含任何额外文字或代码块标记，"
        "格式如下：\n"
        + json.dumps(schema, indent=2, ensure_ascii=False)
        + "\n"
    )


def build_guard_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    schema = {
        "action": "guard",
        "target": "可选，1-12的整数或null。选择你要守护的玩家，null表示空守。",
    }
    user = (
        "现在是夜晚，守卫行动阶段。请基于现有信息（如今天发言、查验结果等）选择一名玩家进行守护，或选择空守。"
        "注意：不能连续两晚守同一个人。"
        + _json_hint(schema)
    )
    return system, user


def build_wolf_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    alive_village = [p.id for p in state.players if p.alive and p.faction.value != "wolf"]
    schema = {
        "action": "wolf_vote_kill",
        "target": "1-12的整数",
        "reason": "简短说明击杀理由（1-2句话）",
    }
    user = (
        "现在是狼人讨论阶段。你和你的狼队友需要选择一名玩家击杀。"
        f"可击杀的目标（非狼人阵营）：{alive_village}\n"
        "请综合考虑威胁等级、神职暴露程度、警徽归属，选择最合适的击杀目标。"
        + _json_hint(schema)
    )
    return system, user


def build_witch_prompt(
    player: Player, state: GameState, night_actions: NightActionSet
) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    kill_target = night_actions.wolf_kill_target
    schema = {
        "action": "witch",
        "use_save": "true/false，是否使用解药救起被狼杀玩家",
        "poison_target": "要毒杀的玩家ID（1-12），不毒人则为 null",
    }

    user_parts = ["现在是女巫行动阶段。"]
    if kill_target and not player.witch_save_used:
        user_parts.append(f"今晚被狼人击杀的玩家是：#{kill_target}")
    if player.witch_save_used:
        user_parts.append("注意：你的解药已经用过了，今晚不会获知狼刀信息。")
    if player.witch_poison_used:
        user_parts.append("注意：你的毒药已经用过了。")
    user_parts.append(
        "请决定是否使用解药救起被杀玩家，以及是否使用毒药毒杀其他玩家。一晚只能用一瓶药。"
    )
    user_parts.append(_json_hint(schema))
    return system, "\n".join(user_parts)


def build_seer_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    candidates = [
        p.id
        for p in state.players
        if p.alive and p.id != player.id and p.id not in player.checked_players
    ]
    schema = {"action": "seer", "target": "1-12的整数，你要查验的玩家"}
    user = (
        "现在是预言家行动阶段。请选择一名玩家进行查验。"
        f"可选目标（未查验且存活）：{candidates if candidates else '所有未查验玩家均不可选，可选其他存活玩家'}\n"
        + _json_hint(schema)
    )
    return system, user


def build_speech_prompt(
    player: Player, state: GameState, round_no: int, public_log: str = ""
) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    schema = {"action": "speech", "content": "你的发言内容（中文，60-200字）"}

    log_section = ""
    if public_log:
        log_section = f"\n本局公开记录（按发生顺序）：\n{public_log}\n"

    role_hint = ""
    if player.faction.value == "wolf":
        role_hint = (
            "你是狼人，请伪装成好人，可以悍跳神职、伪装预言家或村民，"
            "也可以攻击真神位、煽动投票，目的是带偏好人。"
        )
    elif player.role == RoleId.SEER:
        role_hint = "你是预言家，是否跳出来报查验结果由你决定。"
    elif player.role == RoleId.WITCH:
        role_hint = "你是女巫，请谨慎透露夜晚信息，避免暴露自己。"
    elif player.role == RoleId.HUNTER:
        role_hint = "你是猎人，可以适度站边但要小心被狼针对。"
    elif player.role == RoleId.GUARD:
        role_hint = "你是守卫，请隐藏身份避免成为狼刀目标。"
    else:
        role_hint = "你是村民，请仔细分析对位，找出最可疑的玩家。"

    user = (
        f"现在是第 {round_no} 轮的白天发言阶段。轮到你（#{player.id}）发言了。\n"
        + log_section
        + role_hint
        + "\n请基于以上信息进行 60-200 字的中文发言。"
        + _json_hint(schema)
    )
    return system, user


def build_vote_prompt(
    player: Player, state: GameState, vote_state: VoteState | None = None
) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    alive = [p.id for p in state.players if p.alive and p.id != player.id]
    schema = {
        "action": "vote",
        "target": "玩家ID（1-12的整数）或字符串 'abstain' 表示弃票",
    }

    candidates_str = ""
    if vote_state and vote_state.candidates:
        candidates_str = f"本轮只能投票给候选人：{vote_state.candidates}\n"

    user = (
        "现在是放逐投票阶段。请投票选择你认为最可能是狼人的玩家，或选择弃票。"
        f"\n可选目标（存活玩家，不含自己）：{alive}\n"
        + candidates_str
        + _json_hint(schema)
    )
    return system, user


def build_hunter_shoot_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    alive = [p.id for p in state.players if p.alive and p.id != player.id]
    schema = {"action": "hunter_shoot", "target": "玩家ID（1-12的整数）或 null 表示不开枪"}
    user = (
        f"你（猎人）已经死亡。请选择是否发动技能开枪带走一名玩家。"
        f"\n可选目标：{alive}\n"
        + _json_hint(schema)
    )
    return system, user


def build_sheriff_transfer_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    alive = [p.id for p in state.players if p.alive and p.id != player.id]
    schema = {
        "action": "sheriff_transfer",
        "target": "玩家ID（1-12的整数）或字符串 'tear_badge' 表示撕毁警徽",
    }
    user = (
        "你是警长，即将出局。请选择将警徽移交给一名玩家，或撕毁警徽。"
        f"\n可选目标：{alive}\n"
        + _json_hint(schema)
    )
    return system, user


def build_sheriff_run_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    schema = {"action": "sheriff_run", "run": "true 表示上警，false 表示警下"}
    user = (
        "现在是警长竞选阶段（仅第一天进行）。"
        "请决定是否上警争取警徽。神职常常上警传递信息，狼人也可能悍跳混淆视听，"
        "村民通常可以警下保护神位。请基于你的身份与本场局势做出选择。"
        + _json_hint(schema)
    )
    return system, user


def build_last_words_prompt(player: Player, state: GameState) -> tuple[str, str]:
    system = _base_system_prompt(player, state)
    schema = {"action": "last_words", "content": "你的遗言内容（中文，30-150字）"}
    user = (
        "你已经出局，可以留下遗言。请基于你的身份与已知信息，留下对好人或狼人有价值的发言："
        "如果你是预言家或女巫等神职，可以报金水/查杀/用药信息；"
        "如果你是猎人，注意你已经发动过开枪技能；"
        "如果你是狼人，可以选择反水、伪装到底或站边带节奏。"
        + _json_hint(schema)
    )
    return system, user
