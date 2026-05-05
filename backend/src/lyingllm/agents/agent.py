"""Agent orchestrator — calls LLM adapters to produce actions.

Each ``agent_*`` function returns a tuple ``(action, reasoning_text)``.
``reasoning_text`` is either the model's actual chain-of-thought (for
thinking-mode providers like DeepSeek V4) or a synthesized
self-explanation when the model does not return reasoning.
"""

from __future__ import annotations

import asyncio
from typing import Any

from lyingllm.llm.adapters import LLMMessage, LLMRequest, LLMResponse
from lyingllm.llm.registry import get_registry
from lyingllm.agents import prompts
from lyingllm.domain.models.player import Player, RoleId
from lyingllm.domain.models.game import GameState, NightActionSet, VoteState
from lyingllm.domain.models.action import (
    GuardAction,
    WolfVoteKillAction,
    WitchAction,
    SeerAction,
    SpeechAction,
    VoteAction,
    HunterShootAction,
    SheriffTransferAction,
)
from lyingllm.domain.rules.validator import (
    validate_guard,
    default_guard,
    validate_wolf_vote_kill,
    default_wolf_vote_kill,
    validate_witch,
    default_witch,
    validate_seer,
    default_seer,
    validate_vote,
    default_vote,
    validate_hunter_shoot,
    default_hunter_shoot,
    validate_sheriff_transfer,
    default_sheriff_transfer,
)


async def _call_llm(
    player: Player,
    system: str,
    user: str,
    output_schema: dict[str, Any],
    max_retries: int = 2,
) -> LLMResponse:
    """Call the LLM adapter for a player with retry logic."""
    mc = player.model_config
    if mc is None:
        raise RuntimeError(f"Player {player.id} has no model_config")

    registry = get_registry()
    adapter = registry.get(mc.provider_id)
    if adapter is None:
        raise RuntimeError(f"No adapter registered for provider: {mc.provider_id}")

    messages = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]

    request = LLMRequest(
        provider_id=mc.provider_id,
        model_id=mc.model_id,
        messages=messages,
        output_schema=output_schema,
        temperature=getattr(mc, "temperature", None),
        top_p=getattr(mc, "top_p", None),
        max_output_tokens=getattr(mc, "max_output_tokens", 2000),
        timeout_seconds=getattr(mc, "timeout_seconds", 120),
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await adapter.generate(request)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue

    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_error}")


def _has_model_config(player: Player | None) -> bool:
    return player is not None and player.model_config is not None


def _reasoning_text(resp: LLMResponse | None, fallback: str) -> str:
    """Prefer the LLM's actual reasoning trace; fall back to a self-explanation."""
    if resp is not None and resp.reasoning_trace and resp.reasoning_trace.content:
        return resp.reasoning_trace.content.strip()
    return fallback


async def agent_guard(player: Player, state: GameState) -> tuple[GuardAction, str]:
    if not _has_model_config(player):
        action = default_guard(player, state)
        return action, "守卫默认空守，等待局势明朗。"
    system, user = prompts.build_guard_prompt(player, state)
    resp = await _call_llm(player, system, user, {"action": "guard", "target": "int|null"})
    action = default_guard(player, state)
    if resp.parsed_json:
        try:
            candidate = GuardAction(target=resp.parsed_json.get("target"))
            v = validate_guard(candidate, player, state)
            if v:
                action = candidate
        except Exception:
            pass
    fallback = (
        f"守卫选择守护玩家 {action.target}。"
        if action.target is not None
        else "守卫选择空守，观察今晚局势。"
    )
    return action, _reasoning_text(resp, fallback)


async def agent_wolf_vote(player: Player, state: GameState) -> tuple[WolfVoteKillAction, str]:
    if not _has_model_config(player):
        action = default_wolf_vote_kill(player, state)
        return action, f"狼队默认击杀玩家 {action.target}。"
    system, user = prompts.build_wolf_prompt(player, state)
    resp = await _call_llm(
        player, system, user, {"action": "wolf_vote_kill", "target": "int", "reason": "str"}
    )
    action = default_wolf_vote_kill(player, state)
    if resp.parsed_json:
        try:
            data = resp.parsed_json
            candidate = WolfVoteKillAction(
                target=data.get("target", 1), reason=data.get("reason", "")
            )
            v = validate_wolf_vote_kill(candidate, player, state)
            if v:
                action = candidate
        except Exception:
            pass
    fallback = f"狼队决定击杀玩家 {action.target}。原因：{action.reason or '战术权衡。'}"
    return action, _reasoning_text(resp, fallback)


async def agent_witch(
    player: Player, state: GameState, night_actions: NightActionSet
) -> tuple[WitchAction, str]:
    if not _has_model_config(player):
        action = default_witch(player, state, night_actions)
        return action, "女巫默认观望，不使用任何药品。"
    system, user = prompts.build_witch_prompt(player, state, night_actions)
    resp = await _call_llm(
        player,
        system,
        user,
        {"action": "witch", "use_save": "bool", "poison_target": "int|null"},
    )
    action = default_witch(player, state, night_actions)
    if resp.parsed_json:
        try:
            data = resp.parsed_json
            candidate = WitchAction(
                use_save=data.get("use_save", False),
                poison_target=data.get("poison_target"),
            )
            v = validate_witch(candidate, player, state, night_actions)
            if v:
                action = candidate
        except Exception:
            pass
    if action.use_save:
        fallback = f"女巫使用解药救起玩家 {night_actions.wolf_kill_target}。"
    elif action.poison_target is not None:
        fallback = f"女巫使用毒药毒杀玩家 {action.poison_target}。"
    else:
        fallback = "女巫今晚选择不使用任何药品。"
    return action, _reasoning_text(resp, fallback)


async def agent_seer(player: Player, state: GameState) -> tuple[SeerAction, str]:
    if not _has_model_config(player):
        action = default_seer(player, state)
        return action, f"预言家默认查验玩家 {action.target}。"
    system, user = prompts.build_seer_prompt(player, state)
    resp = await _call_llm(player, system, user, {"action": "seer", "target": "int"})
    action = default_seer(player, state)
    if resp.parsed_json:
        try:
            candidate = SeerAction(target=resp.parsed_json.get("target", 1))
            v = validate_seer(candidate, player, state)
            if v:
                action = candidate
        except Exception:
            pass
    target_player = state.get_player(action.target)
    camp = (
        "狼人"
        if (target_player and target_player.faction.value == "wolf")
        else "好人"
    )
    fallback = f"预言家查验玩家 {action.target}，结果为「{camp}」阵营。"
    return action, _reasoning_text(resp, fallback)


async def agent_speech(
    player: Player, state: GameState, round_no: int, public_log: str = ""
) -> tuple[SpeechAction, str]:
    if not _has_model_config(player):
        return SpeechAction(content="（暂无发言）"), "无模型配置，跳过发言。"
    system, user = prompts.build_speech_prompt(player, state, round_no, public_log)
    resp = await _call_llm(player, system, user, {"action": "speech", "content": "str"})
    action = SpeechAction(content="（暂无具体观点。）")
    if resp.parsed_json:
        content = resp.parsed_json.get("content", "")
        if isinstance(content, str) and content.strip():
            action = SpeechAction(content=content.strip())
    fallback = (
        f"思考第 {round_no} 轮的局势后，发表了上述观点。"
    )
    return action, _reasoning_text(resp, fallback)


async def agent_vote(
    player: Player, state: GameState, vote_state: VoteState | None = None
) -> tuple[VoteAction, str]:
    vs = vote_state or VoteState()
    if not _has_model_config(player):
        action = default_vote(player, state, vs)
        return action, "无模型配置，默认弃票。"
    system, user = prompts.build_vote_prompt(player, state, vote_state)
    resp = await _call_llm(player, system, user, {"action": "vote", "target": "int|str"})
    action = default_vote(player, state, vs)
    if resp.parsed_json:
        try:
            candidate = VoteAction(target=resp.parsed_json.get("target", "abstain"))
            v = validate_vote(candidate, player, state, vs)
            if v:
                action = candidate
        except Exception:
            pass
    fallback = (
        f"投票给玩家 {action.target}。"
        if action.target != "abstain"
        else "选择弃票，继续观察。"
    )
    return action, _reasoning_text(resp, fallback)


async def agent_hunter_shoot(
    player: Player, state: GameState
) -> tuple[HunterShootAction, str]:
    if not _has_model_config(player):
        action = default_hunter_shoot(player, state)
        return action, "猎人默认不开枪。"
    system, user = prompts.build_hunter_shoot_prompt(player, state)
    resp = await _call_llm(
        player, system, user, {"action": "hunter_shoot", "target": "int|null"}
    )
    action = default_hunter_shoot(player, state)
    if resp.parsed_json:
        try:
            candidate = HunterShootAction(target=resp.parsed_json.get("target"))
            v = validate_hunter_shoot(candidate, player, state)
            if v:
                action = candidate
        except Exception:
            pass
    fallback = (
        f"猎人开枪带走玩家 {action.target}。"
        if action.target is not None
        else "猎人放弃开枪。"
    )
    return action, _reasoning_text(resp, fallback)


async def agent_sheriff_transfer(
    player: Player, state: GameState
) -> tuple[SheriffTransferAction, str]:
    if not _has_model_config(player):
        action = default_sheriff_transfer(player, state)
        return action, "默认撕毁警徽。"
    system, user = prompts.build_sheriff_transfer_prompt(player, state)
    resp = await _call_llm(
        player, system, user, {"action": "sheriff_transfer", "target": "int|str"}
    )
    action = default_sheriff_transfer(player, state)
    if resp.parsed_json:
        try:
            candidate = SheriffTransferAction(
                target=resp.parsed_json.get("target", "tear_badge")
            )
            v = validate_sheriff_transfer(candidate, player, state)
            if v:
                action = candidate
        except Exception:
            pass
    if action.target == "tear_badge":
        fallback = "警长撕毁警徽。"
    else:
        fallback = f"警长将警徽移交给玩家 {action.target}。"
    return action, _reasoning_text(resp, fallback)


async def agent_sheriff_run(
    player: Player, state: GameState
) -> tuple[bool, str]:
    """Decide whether this player runs for sheriff (上警/警下)."""
    if not _has_model_config(player):
        # Default: gods always run, others stay down
        from lyingllm.domain.models.player import RoleGroup

        decided = player.role_group == RoleGroup.GOD
        return decided, "默认策略：神职上警，其余警下。"
    system, user = prompts.build_sheriff_run_prompt(player, state)
    resp = await _call_llm(player, system, user, {"action": "sheriff_run", "run": "bool"})
    decided = False
    if resp.parsed_json:
        decided = bool(resp.parsed_json.get("run", False))
    fallback = "决定上警争取警徽。" if decided else "决定警下，观察其他人。"
    return decided, _reasoning_text(resp, fallback)


async def agent_last_words(
    player: Player, state: GameState
) -> tuple[str, str]:
    """LLM-generated last words; returns (content, reasoning)."""
    if not _has_model_config(player):
        return "（无遗言）", "无模型配置，跳过遗言。"
    system, user = prompts.build_last_words_prompt(player, state)
    resp = await _call_llm(player, system, user, {"action": "last_words", "content": "str"})
    content = "（保持沉默。）"
    if resp.parsed_json:
        c = resp.parsed_json.get("content", "")
        if isinstance(c, str) and c.strip():
            content = c.strip()
    return content, _reasoning_text(resp, f"留下遗言：{content[:40]}…")
