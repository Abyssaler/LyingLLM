from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.base import Agent
from app.agents.judge import JudgeAI, JudgeConfig
from app.config.loader import YAMLLoader
from app.core.event_bus import EventBus
from app.core.phase import Phase
from app.core.state import GameStateMachine
from app.llm.adapter import AdapterConfig, ProviderAdapter, create_adapter
from app.llm.client import LLMRequest, LLMResponse
from app.llm.retry import RetryPolicy
from app.memory.game_memory import GameMemory
from app.models.event import (
    DeathCause,
    DeathRecord,
    NightActionSet,
    NightResolutionResult,
    PrivateResult,
    VoteRecord,
    VoteResult,
    VoteSummary,
)
from app.models.game import Game
from app.models.player import PlayerStatus
from app.models.role import Faction
from app.roles.base import BaseRole, ActionResult, GameContext
from app.roles import ROLE_REGISTRY, create_role
from app.rules.manager import RuleConfig, RuleManager
from app.storage.game_log import GameLogStorage


@dataclass
class NightActionCollector:
    round: int = 0
    guard_target: Optional[int] = None
    wolf_kill_target: Optional[int] = None
    witch_save_target: Optional[int] = None
    witch_poison_target: Optional[int] = None
    seer_check_target: Optional[int] = None
    wolf_discuss_votes: dict[int, int] = field(default_factory=dict)
    has_guard_action: bool = False
    has_witch_save: bool = False
    has_witch_poison: bool = False
    has_seer_action: bool = False

    def to_action_set(self) -> NightActionSet:
        return NightActionSet(
            round=self.round,
            guard_target=self.guard_target,
            wolf_kill_target=self.wolf_kill_target,
            witch_save_target=self.witch_save_target,
            witch_poison_target=self.witch_poison_target,
            seer_check_target=self.seer_check_target,
        )


@dataclass
class WolfDiscussResult:
    target: int = 0
    votes: dict[int, int] = field(default_factory=dict)
    discussion_summary: str = ""


class GameEngine:
    def __init__(
        self,
        game: Game,
        rules_config: RuleConfig | None = None,
        event_bus: EventBus | None = None,
        log_storage: GameLogStorage | None = None,
    ) -> None:
        self.game = game
        self.state = GameStateMachine()
        self.rules = rules_config or RuleConfig({})
        self.event_bus = event_bus or EventBus()
        self.log = log_storage or GameLogStorage(game_id=game.game_id)
        self.agents: dict[int, Agent] = {}
        self.roles: dict[int, BaseRole] = {}
        self._night_collector: NightActionCollector | None = None
        self._sheriff_id: int | None = None
        self._speech_order: list[int] = []
        self._current_speaker_idx: int = 0
        self._current_voter_idx: int = 0
        self._tied_ids: list[int] = []
        self._revote_count: int = 0
        self._pending_deaths: list[int] = []
        self._last_guard_target: int | None = None
        self._witch_has_save: dict[int, bool] = {}
        self._witch_has_poison: dict[int, bool] = {}
        self._wolf_kill_history: list[int] = field(default_factory=list)
        self._adapter_cache: dict[str, ProviderAdapter] = {}
        self.log.set_config(game.config.model_dump())

    def assign_roles(self, role_assignments: dict[int, str]) -> None:
        for player_id, role_key in role_assignments.items():
            role_instance = create_role(role_key)
            self.roles[player_id] = role_instance
            player = self.game.get_player(player_id)
            if player:
                player.role = role_key
                player.faction = role_instance.faction
        for pid in self.roles:
            if self.roles[pid].faction == Faction.WOLF:
                if isinstance(self.roles[pid], type(self.roles[list(self.roles)[0]])):
                    pass

    def create_agents(self) -> None:
        for player in self.game.players:
            role = self.roles.get(player.player_id)
            faction = role.faction if role else Faction.VILLAGE
            agent = Agent(
                player_id=player.player_id,
                name=player.name,
                role=role,
                faction=faction,
                is_alive=True,
                is_sheriff=player.is_sheriff,
                thinking_mode=player.thinking_mode,
                llm_config=player.llm_config,
            )
            self.agents[player.player_id] = agent
            if role and role.faction == Faction.WOLF:
                wolf_skill = role.get_skill_by_name("kill")
                if wolf_skill and wolf_skill.uses is None:
                    pass
            witch_role = None
            if isinstance(role, type) and role.__name__ == "Witch":
                witch_role = role
            if role and hasattr(role, "has_save_potion"):
                self._witch_has_save[player.player_id] = role.has_save_potion if hasattr(role, "has_save_potion") else True
                self._witch_has_poison[player.player_id] = role.has_poison_potion if hasattr(role, "has_poison_potion") else True

    async def start_game(self) -> Phase:
        result = self.state.start_game(enable_sheriff=self.rules.enable_sheriff)
        await self.event_bus.publish_phase_change("WAITING", self.state.current_phase.value, self.state.round)
        self.log.add_phase_change_event("WAITING", self.state.current_phase.value, self.state.round)
        return result

    async def run_sheriff_election(self) -> Phase:
        self.state.finish_sheriff_election()
        await self._publish_phase("SHERIFF_ELECTION", "NIGHT_BEGIN")
        return self.state.current_phase

    async def run_night_phase(self) -> Phase:
        if self.rules.enable_wolf_discuss and self._has_wolves():
            await self.state.enter_wolf_discuss()
            await self._publish_phase("NIGHT_BEGIN", "WOLF_DISCUSS")
            wolf_result = await self._run_wolf_discuss()
            await self.state.finish_wolf_discuss()
            await self._publish_phase("WOLF_DISCUSS", "NIGHT_ACTIONS")
        else:
            await self.state.skip_wolf_discuss()
            await self._publish_phase("NIGHT_BEGIN", "NIGHT_ACTIONS")

        await self._collect_night_actions()
        await self.state.finish_night_actions()
        await self._publish_phase("NIGHT_ACTIONS", "DAWN")

        resolution = self._resolve_night()
        return await self._process_dawn(resolution)

    async def _has_wolves(self) -> bool:
        alive_wolves = [p for p in self.game.get_alive_players() if p.faction == Faction.WOLF]
        return len(alive_wolves) > 0

    def _has_wolves(self) -> bool:
        return len(self.game.get_alive_wolves()) > 0

    async def _run_wolf_discuss(self) -> WolfDiscussResult:
        alive_wolves = self.game.get_alive_wolves()
        if not alive_wolves:
            return WolfDiscussResult()
        targets = [p.player_id for p in self.game.get_alive_players() if p.faction != Faction.WOLF]
        if not targets:
            return WolfDiscussResult()
        votes: dict[int, int] = {}
        for wolf in alive_wolves:
            target = random.choice(targets)
            votes[wolf.player_id] = target
            self.log.add_night_action_event(
                phase=f"night_{self.state.round}_wolf_discuss",
                round_num=self.state.round,
                player_id=wolf.player_id,
                role="werewolf",
                action_type="wolf_vote",
                target_id=target,
            )
        vote_counts = Counter(votes.values())
        max_votes = max(vote_counts.values())
        top_targets = [t for t, c in vote_counts.items() if c == max_votes]
        chosen_target = random.choice(top_targets)
        for wolf in alive_wolves:
            agent = self.agents.get(wolf.player_id)
            if agent:
                agent.add_faction_memory(
                    f"night_{self.state.round}",
                    "wolf_discuss",
                    f"狼人协商：选择击杀玩家{chosen_target}号",
                    target=chosen_target,
                )
        self.log.add_night_event(
            event_type="wolf_discuss_result",
            phase=f"night_{self.state.round}",
            round_num=self.state.round,
            data={"target": chosen_target, "votes": votes},
        )
        return WolfDiscussResult(target=chosen_target, votes=votes)

    async def _collect_night_actions(self) -> None:
        self._night_collector = NightActionCollector(round=self.state.round)
        alive_players = self.game.get_alive_players()
        night_order = self.rules.night_order
        for role_key in night_order:
            for pid, role in self.roles.items():
                if role.__class__.__name__.lower() != role_key:
                    continue
                player = self.game.get_player(pid)
                if not player or not player.is_alive:
                    continue
                if not role.has_night_action():
                    continue
                context = GameContext(
                    round=self.state.round,
                    phase=f"night_{self.state.round}",
                    alive_player_ids=[p.player_id for p in alive_players],
                    wolf_kill_target=self._night_collector.wolf_kill_target,
                    rules=self.rules.special_rules,
                    extra={"self_player_id": pid},
                )
                if role_key == "guard":
                    context.extra["guard_target"] = context.extra.get("guard_target")
                result = await role.night_action(self.agents.get(pid), context)
                self._apply_night_action(role_key, pid, result)

    def _apply_night_action(self, role_key: str, player_id: int, result: ActionResult) -> None:
        if not self._night_collector:
            return
        if result.success:
            if role_key == "guard":
                self._night_collector.guard_target = result.target_id
                self._night_collector.has_guard_action = True
            elif role_key == "werewolf":
                self._night_collector.wolf_kill_target = result.target_id
            elif role_key == "witch":
                if result.data.get("save_target"):
                    self._night_collector.witch_save_target = result.data["save_target"]
                    self._night_collector.has_witch_save = True
                if result.data.get("poison_target"):
                    self._night_collector.witch_poison_target = result.data["poison_target"]
                    self._night_collector.has_witch_poison = True
            elif role_key == "seer":
                self._night_collector.seer_check_target = result.target_id
                self._night_collector.has_seer_action = True

        self.log.add_night_action_event(
            phase=f"night_{self.state.round}",
            round_num=self.state.round,
            player_id=player_id,
            role=role_key,
            action_type=result.action_type,
            target_id=result.target_id,
            data=result.data,
        )

    def _resolve_night(self) -> NightResolutionResult:
        nc = self._night_collector
        if nc is None:
            nc = NightActionCollector(round=self.state.round)
        deaths: list[DeathRecord] = []
        death_causes: list[DeathRecord] = []
        private_results: list[PrivateResult] = []

        wolf_target = nc.wolf_kill_target
        actually_dies: dict[int, list[DeathCause]] = {}

        if wolf_target is not None:
            is_protected = False
            if nc.has_guard_action and nc.guard_target == wolf_target:
                if self.rules.guard_blocks_wolf_kill:
                    is_protected = True
            if nc.has_witch_save and nc.witch_save_target == wolf_target:
                if self.rules.witch_save_blocks_wolf_kill:
                    is_protected = True
                    private_results.append(PrivateResult(
                        player_id=nc.witch_save_target or 0,
                        result_type="witch_save",
                        data={"saved_target": wolf_target},
                    ))
            if nc.has_guard_action and nc.has_witch_save and nc.guard_target == wolf_target and nc.witch_save_target == wolf_target:
                if self.rules.guard_witch_same_target_dies:
                    is_protected = False
            if not is_protected:
                actually_dies.setdefault(wolf_target, []).append(DeathCause.WOLF_KILL)
            for agent_id in self.agents:
                if self.agents[agent_id].is_wolf:
                    self.agents[agent_id].add_faction_memory(
                        f"night_{self.state.round}",
                        "wolf_kill",
                        f"狼人击杀目标：玩家{wolf_target}号，{'成功' if not is_protected else '被守护/解救'}",
                    )

        if nc.has_witch_poison and nc.witch_poison_target is not None:
            actually_dies.setdefault(nc.witch_poison_target, []).append(DeathCause.WITCH_POISON)

        for pid, causes in actually_dies.items():
            death_record = DeathRecord(player_id=pid, causes=causes)
            deaths.append(death_record)
            death_causes.append(death_record)

        if nc.has_seer_action and nc.seer_check_target is not None:
            target_player = self.game.get_player(nc.seer_check_target)
            is_wolf = target_player.faction == Faction.WOLF if target_player else False
            private_results.append(PrivateResult(
                player_id=nc.seer_check_target,
                result_type="seer_check",
                data={"target": nc.seer_check_target, "is_wolf": is_wolf},
            ))
            seer_agent = None
            for pid, role in self.roles.items():
                if role.__class__.__name__ == "Seer":
                    player = self.game.get_player(pid)
                    if player and player.is_alive:
                        seer_agent = self.agents.get(pid)
                        break
            if seer_agent:
                seer_agent.add_private_memory(
                    f"night_{self.state.round}",
                    "seer_check",
                    f"查验玩家{nc.seer_check_target}号：{'狼人' if is_wolf else '好人'}",
                    target=nc.seer_check_target,
                    is_wolf=is_wolf,
                )

        dead_ids = [d.player_id for d in deaths]
        if dead_ids:
            announcement = f"昨夜，玩家{'、'.join(f'{pid}号' for pid in dead_ids)}死亡。"
        else:
            announcement = "昨夜是平安夜，没有玩家死亡。"

        for pid_or_agent in self.agents:
            agent = self.agents[pid_or_agent]
            agent.add_public_memory(
                f"night_{self.state.round}",
                "dawn_announcement",
                announcement,
            )

        return NightResolutionResult(
            deaths=deaths,
            death_causes=death_causes,
            private_results=private_results,
            public_announcement=announcement,
        )

    async def _process_dawn(self, resolution: NightResolutionResult) -> Phase:
        self.log.add_night_resolution(self.state.round, resolution)
        for pid in [d.player_id for d in resolution.deaths]:
            player = self.game.get_player(pid)
            if player:
                player.status = PlayerStatus.DEAD
                causes = [d.causes for d in resolution.deaths if d.player_id == pid][0]
                player.death_cause = [c.value for c in causes]
                player.death_round = self.state.round
            agent = self.agents.get(pid)
            if agent:
                agent.is_alive = False

        self._pending_deaths = [d.player_id for d in resolution.deaths]
        has_deaths = len(resolution.deaths) > 0
        has_death_skill = any(
            self._player_has_death_skill(d.player_id, resolution)
            for d in resolution.deaths
        )
        is_first_night = self.state.round == 1
        enable_last_words = self.rules.enable_last_words
        if is_first_night and not self.rules.first_night_has_last_words:
            enable_last_words = False

        has_last_words = has_deaths and enable_last_words
        return self.state.resolve_dawn(
            has_deaths=has_deaths,
            has_last_words=has_last_words,
            has_death_skill=has_death_skill,
        )

    def _player_has_death_skill(self, player_id: int, resolution: NightResolutionResult = None) -> bool:
        role = self.roles.get(player_id)
        if role and role.has_on_death_skill():
            return True
        player = self.game.get_player(player_id)
        if player and player.is_sheriff and self.rules.sheriff_can_transfer:
            return True
        return False

    async def run_win_check(self, after_night: bool) -> Phase:
        alive_wolves = self.game.get_alive_wolves()
        alive_villagers = self.game.get_alive_villagers()
        if len(alive_wolves) == 0:
            return self.state.check_win(has_winner=True, after_night=after_night)
        if len(alive_wolves) >= len(alive_villagers):
            return self.state.check_win(has_winner=True, after_night=after_night)
        return self.state.check_win(has_winner=False, after_night=after_night)

    async def run_day_phase(self) -> Phase:
        await self.state.start_discuss()
        await self._publish_phase("DISCUSS_ORDER", "DISCUSS")
        await self._run_discuss()
        await self.state.finish_discuss()
        await self._publish_phase("DISCUSS", "VOTE")
        await self._run_vote()
        await self.state.finish_vote()
        await self._publish_phase("VOTE", "VOTE_RESULT")
        return await self._resolve_vote()

    def _determine_speech_order(self) -> list[int]:
        alive_players = self.game.get_alive_players()
        if not alive_players:
            return []
        if self._sheriff_id:
            sheriff_player = self.game.get_player(self._sheriff_id)
            if sheriff_player and sheriff_player.is_alive:
                start = random.choice([p.player_id for p in alive_players])
                sorted_alive = sorted([p.player_id for p in alive_players])
                idx = sorted_alive.index(start) if start in sorted_alive else 0
                return sorted_alive[idx:] + sorted_alive[:idx]
        start = random.choice([p.player_id for p in alive_players])
        sorted_alive = sorted([p.player_id for p in alive_players])
        idx = sorted_alive.index(start) if start in sorted_alive else 0
        return sorted_alive[idx:] + sorted_alive[:idx]

    async def _run_discuss(self) -> None:
        self._speech_order = self._determine_speech_order()
        for player_id in self._speech_order:
            agent = self.agents.get(player_id)
            if agent and agent.is_alive:
                self.log.add_speech_event(
                    phase=f"day_{self.state.round}_discuss",
                    round_num=self.state.round,
                    player_id=player_id,
                    content=f"[玩家{player_id}号发言]",
                )
                agent.add_public_memory(
                    f"day_{self.state.round}",
                    "discuss",
                    f"玩家{player_id}号在讨论阶段发言",
                )

    async def _run_vote(self) -> None:
        alive_players = self.game.get_alive_players()
        self._speech_order = sorted([p.player_id for p in alive_players])
        for player_id in self._speech_order:
            agent = self.agents.get(player_id)
            if agent and agent.is_alive:
                self.log.add_vote_event(
                    phase=f"day_{self.state.round}_vote",
                    round_num=self.state.round,
                    player_id=player_id,
                    target_id=0,
                )

    def _count_votes(self, votes: list[VoteRecord]) -> VoteSummary:
        vote_counts: Counter[int] = Counter()
        abstain_count = 0
        total_weight = 0.0

        for vote in votes:
            if vote.is_abstain or vote.target_id is None:
                abstain_count += 1
                player = self.game.get_player(vote.voter_id)
                if player and player.is_sheriff:
                    total_weight += self.rules.sheriff_vote_weight
                else:
                    total_weight += 1.0
                continue
            player = self.game.get_player(vote.voter_id)
            weight = self.rules.sheriff_vote_weight if (player and player.is_sheriff) else 1.0
            vote_counts[vote.target_id] += weight
            total_weight += weight

        if not vote_counts and abstain_count == len(votes):
            return VoteSummary(
                round=self.state.round,
                votes=votes,
                result=VoteResult.ALL_ABSTAIN,
                eliminated_id=None,
                tied_ids=[],
            )

        if not vote_counts:
            return VoteSummary(
                round=self.state.round,
                votes=votes,
                result=VoteResult.ALL_ABSTAIN,
                eliminated_id=None,
                tied_ids=[],
            )

        max_votes = max(vote_counts.values())
        top_candidates = [pid for pid, count in vote_counts.items() if count == max_votes]

        if self.rules.vote_type == "majority" and len(top_candidates) == 1:
            threshold = total_weight / 2
            if max_votes > threshold:
                return VoteSummary(
                    round=self.state.round,
                    votes=votes,
                    result=VoteResult.MAJORITY,
                    eliminated_id=top_candidates[0],
                    tied_ids=[],
                )

        if len(top_candidates) > 1:
            return VoteSummary(
                round=self.state.round,
                votes=votes,
                result=VoteResult.TIE,
                eliminated_id=None,
                tied_ids=top_candidates,
            )

        if self.rules.vote_type == "plurality":
            return VoteSummary(
                round=self.state.round,
                votes=votes,
                result=VoteResult.MAJORITY,
                eliminated_id=top_candidates[0],
                tied_ids=[],
            )

        if max_votes > total_weight / 2:
            return VoteSummary(
                round=self.state.round,
                votes=votes,
                result=VoteResult.MAJORITY,
                eliminated_id=top_candidates[0],
            )

        if len(top_candidates) == 1:
            return VoteSummary(
                round=self.state.round,
                votes=votes,
                result=VoteResult.MAJORITY,
                eliminated_id=top_candidates[0],
            )

        return VoteSummary(
            round=self.state.round,
            votes=votes,
            result=VoteResult.TIE,
            eliminated_id=None,
            tied_ids=top_candidates,
        )

    async def _resolve_vote(self) -> Phase:
        votes: list[VoteRecord] = []
        alive_players = self.game.get_alive_players()
        for voter in alive_players:
            votes.append(VoteRecord(voter_id=voter.player_id, target_id=None, is_abstain=True))
        summary = self._count_votes(votes)
        self.log.add_vote_result_event(
            phase=f"day_{self.state.round}_vote_result",
            round_num=self.state.round,
            vote_summary=summary,
        )

        if summary.result == VoteResult.MAJORITY:
            return await self._process_majority(summary)
        elif summary.result == VoteResult.TIE:
            return await self._process_tie(summary)
        else:
            return self.state.resolve_vote_result("all_abstain")

    async def _process_majority(self, summary: VoteSummary) -> Phase:
        self.state.resolve_vote_result("majority")
        await self._publish_phase("VOTE_RESULT", "EXECUTE")
        eliminated_id = summary.eliminated_id
        if eliminated_id is not None:
            player = self.game.get_player(eliminated_id)
            if player:
                player.status = PlayerStatus.DEAD
                player.death_cause = [DeathCause.VOTE_EXECUTE.value]
                player.death_round = self.state.round
            agent = self.agents.get(eliminated_id)
            if agent:
                agent.is_alive = False
            for other_id in self.agents:
                self.agents[other_id].add_public_memory(
                    f"day_{self.state.round}",
                    "execute",
                    f"玩家{eliminated_id}号被投票处决",
                )
            has_last_words = self.rules.enable_last_words
            has_death_skill = self._player_has_death_skill(eliminated_id)
            return self.state.finish_execute(
                has_last_words=has_last_words,
                has_death_skill=has_death_skill,
            )
        return self.state.finish_execute(has_last_words=False, has_death_skill=False)

    async def _process_tie(self, summary: VoteSummary) -> Phase:
        self._tied_ids = summary.tied_ids
        self._revote_count = 0
        return await self._run_tie_flow()

    async def _run_tie_flow(self) -> Phase:
        while self._revote_count < self.rules.max_revote_rounds:
            self.state.resolve_vote_result("tie")
            await self._publish_phase("VOTE_RESULT", "TIE_SPEECH")
            for player_id in sorted(self._tied_ids):
                player = self.game.get_player(player_id)
                if player and player.is_alive:
                    self.log.add_speech_event(
                        phase=f"day_{self.state.round}_tie_speech",
                        round_num=self.state.round,
                        player_id=player_id,
                        content=f"[平票玩家{player_id}号发言]",
                    )
            self.state.finish_tie_speech()
            await self._publish_phase("TIE_SPEECH", "TIE_VOTE")

            votes: list[VoteRecord] = []
            alive_players = self.game.get_alive_players()
            for p in alive_players:
                if p.player_id not in self._tied_ids:
                    votes.append(VoteRecord(voter_id=p.player_id, target_id=None))
            tie_summary = self._count_votes(votes)

            self.state.finish_tie_vote()
            await self._publish_phase("TIE_VOTE", "VOTE_RESULT")

            if tie_summary.result == VoteResult.MAJORITY:
                return await self._process_majority(tie_summary)
            elif tie_summary.result == VoteResult.TIE:
                new_tied = tie_summary.tied_ids
                if new_tied:
                    self._tied_ids = new_tied
                self._revote_count += 1
                continue
            else:
                return self.state.resolve_vote_result("all_abstain")

        if self.rules.final_tie_resolution == "no_elimination":
            return self.state.resolve_vote_result("all_abstain")
        elif self.rules.final_tie_resolution == "random_elimination":
            eliminated = random.choice(self._tied_ids)
            player = self.game.get_player(eliminated)
            if player:
                player.status = PlayerStatus.DEAD
                player.death_cause = [DeathCause.VOTE_EXECUTE.value]
                player.death_round = self.state.round
            agent = self.agents.get(eliminated)
            if agent:
                agent.is_alive = False
            return self.state.resolve_vote_result("majority")
        return self.state.resolve_vote_result("all_abstain")

    async def run_last_words(self, dead_player_ids: list[int]) -> Phase:
        for pid in sorted(dead_player_ids):
            player = self.game.get_player(pid)
            if player:
                self.log.add_last_words_event(
                    phase=f"last_words_{self.state.round}",
                    round_num=self.state.round,
                    player_id=pid,
                    content=f"[玩家{pid}号遗言]",
                )
                for other_id in self.agents:
                    self.agents[other_id].add_public_memory(
                        f"day_{self.state.round}",
                        "last_words",
                        f"玩家{pid}号发表遗言",
                    )
        has_death_skill = any(self._player_has_death_skill(pid) for pid in dead_player_ids)
        return self.state.finish_last_words(has_death_skill=has_death_skill)

    async def run_on_death_skill(self, dead_player_ids: list[int]) -> Phase:
        self.state.finish_on_death_skill.__func__
        for pid in sorted(dead_player_ids):
            role = self.roles.get(pid)
            player = self.game.get_player(pid)
            if not player:
                continue
            has_death_skill = role and role.has_on_death_skill()
            is_sheriff = player.is_sheriff and self.rules.sheriff_can_transfer

            if has_death_skill:
                context = GameContext(
                    round=self.state.round,
                    phase="on_death_skill",
                    alive_player_ids=[p.player_id for p in self.game.get_alive_players()],
                    extra={
                        "self_player_id": pid,
                        "death_causes": player.death_cause or [],
                    },
                    rules=self.rules.special_rules,
                )
                result = await role.on_death(self.agents.get(pid), context)
                if result and result.success:
                    self.log.add_on_death_skill_event(
                        phase="on_death_skill",
                        round_num=self.state.round,
                        player_id=pid,
                        skill_type=result.action_type,
                        target_id=result.target_id,
                    )
                    if result.target_id is not None:
                        target_player = self.game.get_player(result.target_id)
                        if target_player and not has_death_skill:
                            pass
                        if result.action_type == "shoot" and result.target_id:
                            target = self.game.get_player(result.target_id)
                            if target:
                                target.status = PlayerStatus.DEAD
                                target.death_cause = [DeathCause.HUNTER_SHOOT.value]
                                target.death_round = self.state.round
                            target_agent = self.agents.get(result.target_id)
                            if target_agent:
                                target_agent.is_alive = False

            if is_sheriff:
                alive_ids = [p.player_id for p in self.game.get_alive_players()]
                if alive_ids:
                    transfer_target = random.choice(alive_ids)
                    target_player = self.game.get_player(transfer_target)
                    if target_player:
                        target_player.is_sheriff = True
                    player.is_sheriff = False
                    self._sheriff_id = transfer_target
                    self.log.add_on_death_skill_event(
                        phase="on_death_skill",
                        round_num=self.state.round,
                        player_id=pid,
                        skill_type="sheriff_transfer",
                        sheriff_transfer=transfer_target,
                    )

        return self.state.finish_on_death_skill()

    async def end_game(self, winner: str) -> dict[str, Any]:
        self.state.end_game()
        self.game.winner = winner
        self.game.current_phase = Phase.GAME_END.value
        rounds = self.state.round
        self.log.set_result(winner, rounds)
        result = {"winner": winner, "rounds": rounds, "mvp": None}
        return result

    async def run_mvp_evaluation(
        self,
        judge: JudgeAI,
        winner: str,
    ) -> dict[str, Any] | None:
        log = self.log.build_log()
        log_text = f"胜方：{winner}\n\n"
        for event in log.day_log:
            log_text += f"[R{event.round}/{event.phase}] {event.event_type}: P{event.player_id} - {event.data}\n"
        alive_ids = [p.player_id for p in self.game.get_alive_players()]
        all_ids = [p.player_id for p in self.game.players]
        mvp_result = await judge.evaluate_mvp(
            winner=winner,
            rounds=self.state.round,
            game_log_text=log_text,
            alive_player_ids=alive_ids,
            all_player_ids=all_ids,
        )
        if mvp_result and mvp_result.get("mvp_player_id") is not None:
            player = self.game.get_player(mvp_result["mvp_player_id"])
            role = self.roles.get(mvp_result["mvp_player_id"])
            self.log.set_mvp(
                player_id=mvp_result["mvp_player_id"],
                role=role.name if role else "unknown",
                model=player.llm_config.model_name if player and player.llm_config else "unknown",
                reason=mvp_result.get("reason", ""),
            )
            self.game.mvp_player_id = mvp_result["mvp_player_id"]
            self.game.mvp_reason = mvp_result.get("reason", "")
        return mvp_result

    async def _publish_phase(self, from_phase: str, to_phase: str) -> None:
        await self.event_bus.publish_phase_change(
            from_phase=from_phase,
            to_phase=to_phase,
            round=self.state.round,
        )
        self.log.add_phase_change_event(from_phase, to_phase, self.state.round)

    def save_log(self, filepath: str | None = None) -> str:
        path = self.log.save_to_file(filepath)
        return str(path)

    async def pause(self) -> Phase:
        return self.state.pause()

    async def resume(self) -> Phase:
        return self.state.resume()

    async def abort(self, reason: str = "") -> Phase:
        return self.state.abort(reason=reason)