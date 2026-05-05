"""Game runner — the only module that mutates GameState.

Drives the fixed state machine from ``SETUP`` to ``GAME_END``.  Each phase
handler may invoke LLM agents, validate actions, emit events, and
transition to the next phase.
"""

from __future__ import annotations

import random
from typing import Awaitable, Callable

from lyingllm.domain.models.action import SheriffTransferAction
from lyingllm.domain.models.event import GameEvent
from lyingllm.domain.models.game import (
    DeathCause,
    DeathRecord,
    GameSetupConfig,
    GameState,
    NightActionSet,
    Phase,
    SheriffElectionState,
    VoteState,
)
from lyingllm.domain.models.player import Player, RoleGroup, RoleId
from lyingllm.domain.rules.roles import assign_roles
from lyingllm.engine.resolver import check_win, resolve_night
from lyingllm.storage.event_log import EventLog
from lyingllm.agents import agent as agent_module


class GameRunner:
    def __init__(
        self,
        game_id: str,
        setup: GameSetupConfig,
        seed: int = 42,
    ) -> None:
        self.state = GameState(game_id=game_id)
        self.setup = setup
        self.events = EventLog()
        self.rng = random.Random(seed)
        self._handlers: dict[Phase, Callable[[], Awaitable[None]]] = {
            Phase.SETUP: self._handle_setup,
            Phase.ROLE_ASSIGNMENT: self._handle_role_assignment,
            Phase.NIGHT_BEGIN: self._handle_night_begin,
            Phase.GUARD_ACTION: self._handle_guard_action,
            Phase.WOLF_DISCUSS: self._handle_wolf_discuss,
            Phase.WITCH_ACTION: self._handle_witch_action,
            Phase.SEER_ACTION: self._handle_seer_action,
            Phase.NIGHT_RESOLVE: self._handle_night_resolve,
            Phase.DAWN: self._handle_dawn,
            Phase.FIRST_DAY_SHERIFF_GATE: self._handle_first_day_sheriff_gate,
            Phase.SHERIFF_ELECTION: self._handle_sheriff_election,
            Phase.SHERIFF_SPEECH: self._handle_sheriff_speech,
            Phase.SHERIFF_VOTE: self._handle_sheriff_vote,
            Phase.SHERIFF_RESULT: self._handle_sheriff_result,
            Phase.DEATH_SKILL: self._handle_death_skill,
            Phase.SHERIFF_TRANSFER: self._handle_sheriff_transfer,
            Phase.LAST_WORDS: self._handle_last_words,
            Phase.WIN_CHECK: self._handle_win_check,
            Phase.DISCUSS_ORDER: self._handle_discuss_order,
            Phase.DISCUSS: self._handle_discuss,
            Phase.VOTE: self._handle_vote,
            Phase.VOTE_RESULT: self._handle_vote_result,
            Phase.TIE_SPEECH: self._handle_tie_speech,
            Phase.TIE_VOTE: self._handle_tie_vote,
            Phase.EXILE: self._handle_exile,
            Phase.NO_ELIMINATION: self._handle_no_elimination,
            Phase.SELF_DESTRUCT: self._handle_self_destruct,
            Phase.DAY_ABORTED: self._handle_day_aborted,
            Phase.GAME_END: self._handle_game_end,
        }

        # Mutable engine-only state
        self._speech_queue: list[int] = []
        self._speech_index: int = 0
        self._sheriff_speech_queue: list[int] = []
        self._sheriff_speech_index: int = 0
        self._sheriff_candidates: list[int] = []
        self._sheriff_withdrawn: list[int] = []
        self._sheriff_transfer_pid: int | None = None
        self._post_death_phase: Phase = Phase.DISCUSS_ORDER
        # Death records resolved in the current death-processing cycle —
        # consumed and cleared by ``_handle_last_words``.
        self._completed_deaths: list[DeathRecord] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def step(self) -> bool:
        """Advance one phase.  Returns ``True`` when the game has ended."""
        if self.state.phase == Phase.GAME_END:
            return True
        handler = self._handlers[self.state.phase]
        await handler()
        return self.state.phase == Phase.GAME_END

    async def run(self) -> None:
        while not await self.step():
            pass

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _emit(
        self,
        event_type: str,
        data: dict,
        visibility: list[str],
        player_id: int | None = None,
    ) -> GameEvent:
        event = GameEvent(
            event_id=self.events.next_id(),
            game_id=self.state.game_id,
            round_no=self.state.round_no,
            phase=self.state.phase,
            event_type=event_type,
            player_id=player_id,
            visibility=visibility,
            data=data,
        )
        self.events.append(event)
        return event

    def _transition(self, phase: Phase) -> None:
        old = self.state.phase
        self.state.phase = phase
        self._emit(
            "phase_change",
            {"from": old.value, "to": phase.value},
            ["observer"],
        )

    def _emit_reasoning(
        self,
        player_id: int,
        action: str,
        content: str,
        mode: str = "self_explanation",
    ) -> None:
        if not content:
            return
        self._emit(
            "reasoning_trace",
            {
                "mode": mode,
                "player_id": player_id,
                "action": action,
                "content": content,
            },
            ["observer", f"player:{player_id}"],
            player_id=player_id,
        )

    def _emit_invocation_start(self, player_id: int, action: str) -> None:
        self._emit(
            "agent_invocation_start",
            {"player_id": player_id, "action": action},
            ["observer", f"player:{player_id}"],
            player_id=player_id,
        )

    def _alive_ids(self) -> list[int]:
        return [p.id for p in self.state.players if p.alive]

    def _find_player(self, role: RoleId) -> Player | None:
        for p in self.state.players:
            if p.role == role and p.alive:
                return p
        return None

    def _find_players(self, *roles: RoleId) -> list[Player]:
        return [p for p in self.state.players if p.role in roles and p.alive]

    def _build_public_log(self) -> str:
        """A short public log of speeches and votes the LLM can read."""
        lines: list[str] = []
        for e in self.events.public_view()[-80:]:
            if e.event_type == "speech":
                pid = e.player_id
                content = e.data.get("content", "")
                if content:
                    lines.append(f"第{e.round_no}轮 #{pid} 发言：{content}")
            elif e.event_type == "vote":
                ballots = e.data.get("ballots") or {}
                vt = e.data.get("type", "exile")
                if ballots:
                    lines.append(
                        f"第{e.round_no}轮 {vt}投票：" +
                        ", ".join(f"#{v}→{t}" for v, t in ballots.items())
                    )
            elif e.event_type == "exile":
                lines.append(f"第{e.round_no}轮 玩家 #{e.data.get('player_id')} 被放逐")
            elif e.event_type == "dawn":
                dead = e.data.get("dead_players", [])
                lines.append(f"第{e.round_no}轮天亮：夜间死亡 {dead}")
            elif e.event_type == "sheriff_result":
                sid = e.data.get("sheriff_id")
                lines.append(f"警长归属：{'#' + str(sid) if sid else '撕警徽'}")
        return "\n".join(lines[-30:])

    # ------------------------------------------------------------------ #
    # Phase handlers
    # ------------------------------------------------------------------ #
    async def _handle_setup(self) -> None:
        self._emit("game_start", {"game_id": self.state.game_id}, ["public", "observer"])
        self._transition(Phase.ROLE_ASSIGNMENT)

    async def _handle_role_assignment(self) -> None:
        roles = assign_roles(rng=self.rng)
        players: list[Player] = []
        for i, role in enumerate(roles):
            pid = i + 1
            setup = next((s for s in self.setup.players if s.player_id == pid), None)
            players.append(
                Player(
                    id=pid,
                    role=role,
                    model_config=setup.model_config if setup else None,
                )
            )
        self.state.players = players
        self._emit(
            "role_assignment",
            {
                "assignments": [
                    {"player_id": p.id, "role": p.role.value} for p in players
                ]
            },
            ["observer"],
        )
        self._transition(Phase.NIGHT_BEGIN)

    async def _handle_night_begin(self) -> None:
        self.state.round_no += 1
        self.state.night_actions = NightActionSet(round_no=self.state.round_no)
        self._emit(
            "night_begin",
            {"round_no": self.state.round_no},
            ["public", "observer"],
        )
        self._transition(Phase.GUARD_ACTION)

    async def _handle_guard_action(self) -> None:
        guard = self._find_player(RoleId.GUARD)
        if guard is None:
            self.state.night_actions.guard_target = None
        else:
            self._emit_invocation_start(guard.id, "guard")
            action, reasoning = await agent_module.agent_guard(guard, self.state)
            guard.last_guard_target = action.target
            self.state.night_actions.guard_target = action.target
            self._emit(
                "night_action",
                action.to_dict(),
                ["observer", f"player:{guard.id}"],
                player_id=guard.id,
            )
            self._emit_reasoning(guard.id, "guard", reasoning, mode=_reason_mode(guard))
        self._transition(Phase.WOLF_DISCUSS)

    async def _handle_wolf_discuss(self) -> None:
        wolves = self._find_players(RoleId.WEREWOLF, RoleId.WHITE_WOLF_KING)
        if not wolves:
            self.state.night_actions.wolf_kill_target = None
        else:
            speaker = wolves[0]
            self._emit_invocation_start(speaker.id, "wolf_vote_kill")
            action, reasoning = await agent_module.agent_wolf_vote(speaker, self.state)
            self.state.night_actions.wolf_kill_target = action.target
            visibility = ["observer", "wolves"] + [f"player:{w.id}" for w in wolves]
            self._emit(
                "night_action",
                action.to_dict(),
                visibility,
                player_id=speaker.id,
            )
            self._emit_reasoning(
                speaker.id, "wolf_vote_kill", reasoning, mode=_reason_mode(speaker)
            )
        self._transition(Phase.WITCH_ACTION)

    async def _handle_witch_action(self) -> None:
        witch = self._find_player(RoleId.WITCH)
        if witch is None:
            self.state.night_actions.witch_save_used = False
            self.state.night_actions.witch_poison_target = None
        else:
            self._emit_invocation_start(witch.id, "witch")
            action, reasoning = await agent_module.agent_witch(
                witch, self.state, self.state.night_actions
            )
            if action.use_save:
                witch.witch_save_used = True
            if action.poison_target is not None:
                witch.witch_poison_used = True
            self.state.night_actions.witch_save_used = action.use_save
            self.state.night_actions.witch_poison_target = action.poison_target
            self._emit(
                "night_action",
                action.to_dict(),
                ["observer", f"player:{witch.id}"],
                player_id=witch.id,
            )
            self._emit_reasoning(witch.id, "witch", reasoning, mode=_reason_mode(witch))
        self._transition(Phase.SEER_ACTION)

    async def _handle_seer_action(self) -> None:
        seer = self._find_player(RoleId.SEER)
        if seer is None:
            self.state.night_actions.seer_check_target = None
        else:
            self._emit_invocation_start(seer.id, "seer")
            action, reasoning = await agent_module.agent_seer(seer, self.state)
            seer.checked_players.add(action.target)
            self.state.night_actions.seer_check_target = action.target
            target_player = self.state.get_player(action.target)
            result_camp = (
                "wolf"
                if (target_player and target_player.faction.value == "wolf")
                else "village"
            )
            self._emit(
                "night_action",
                {**action.to_dict(), "result": result_camp},
                ["observer", f"player:{seer.id}"],
                player_id=seer.id,
            )
            self._emit_reasoning(seer.id, "seer", reasoning, mode=_reason_mode(seer))
        self._transition(Phase.NIGHT_RESOLVE)

    async def _handle_night_resolve(self) -> None:
        deaths = resolve_night(self.state, self.state.night_actions)
        self.state.death_queue.extend(deaths)
        self._emit(
            "night_resolution",
            {
                "deaths": [
                    {"player_id": d.player_id, "causes": [c.value for c in d.causes]}
                    for d in deaths
                ]
            },
            ["observer"],
        )
        self._transition(Phase.DAWN)

    async def _handle_dawn(self) -> None:
        dead_ids = [d.player_id for d in self.state.death_queue]
        self._emit(
            "dawn",
            {"dead_players": dead_ids, "round_no": self.state.round_no},
            ["public", "observer"],
        )
        if self.state.is_first_night:
            self._transition(Phase.FIRST_DAY_SHERIFF_GATE)
        else:
            self._post_death_phase = Phase.DISCUSS_ORDER
            self._transition(Phase.DEATH_SKILL)

    # ---- Sheriff election (day 1) ------------------------------------- #
    async def _handle_first_day_sheriff_gate(self) -> None:
        self._transition(Phase.SHERIFF_ELECTION)

    async def _handle_sheriff_election(self) -> None:
        """Ask each alive player whether they want to run for sheriff."""
        candidates: list[int] = []
        for p in self.state.players:
            if not p.alive:
                continue
            if p.model_config is None:
                # Default policy: gods + wolves run, villagers stay down
                run = p.role_group in (RoleGroup.GOD, RoleGroup.WOLF)
                reasoning = "默认策略：神/狼上警博弈，村民警下。"
            else:
                self._emit_invocation_start(p.id, "sheriff_run")
                run, reasoning = await agent_module.agent_sheriff_run(p, self.state)
            self._emit(
                "sheriff_decision",
                {"player_id": p.id, "run": bool(run)},
                ["public", "observer"],
                player_id=p.id,
            )
            self._emit_reasoning(p.id, "sheriff_run", reasoning, mode=_reason_mode(p))
            if run:
                candidates.append(p.id)

        # Edge case: nobody runs → no sheriff this game
        if not candidates:
            self._emit(
                "sheriff_result",
                {"sheriff_id": None, "reason": "no_candidates"},
                ["public", "observer"],
            )
            self._post_death_phase = Phase.DISCUSS_ORDER
            self._transition(Phase.DEATH_SKILL)
            return

        self._sheriff_candidates = candidates
        self._sheriff_withdrawn = []
        self._sheriff_speech_queue = list(candidates)
        self._sheriff_speech_index = 0
        self._emit(
            "sheriff_election",
            {"candidates": candidates},
            ["public", "observer"],
        )
        self._transition(Phase.SHERIFF_SPEECH)

    async def _handle_sheriff_speech(self) -> None:
        """Process one candidate's campaign speech per step."""
        if self._sheriff_speech_index >= len(self._sheriff_speech_queue):
            self._transition(Phase.SHERIFF_VOTE)
            return
        speaker_id = self._sheriff_speech_queue[self._sheriff_speech_index]
        self._sheriff_speech_index += 1
        speaker = self.state.get_player(speaker_id)
        if speaker and speaker.alive:
            self._emit_invocation_start(speaker.id, "sheriff_speech")
            action, reasoning = await agent_module.agent_speech(
                speaker, self.state, self.state.round_no, self._build_public_log()
            )
            self._emit(
                "speech",
                {**action.to_dict(), "context": "sheriff_speech"},
                ["public", "observer"],
                player_id=speaker_id,
            )
            self._emit_reasoning(
                speaker_id, "sheriff_speech", reasoning, mode=_reason_mode(speaker)
            )

    async def _handle_sheriff_vote(self) -> None:
        alive = self._alive_ids()
        voters = [pid for pid in alive if pid not in self._sheriff_candidates]
        ballots: dict[int, int] = {}
        vs = VoteState(candidates=list(self._sheriff_candidates))
        for pid in voters:
            voter = self.state.get_player(pid)
            if voter is None or not voter.alive:
                continue
            self._emit_invocation_start(pid, "sheriff_vote")
            action, reasoning = await agent_module.agent_vote(voter, self.state, vs)
            target = action.target
            if not isinstance(target, int) or target not in self._sheriff_candidates:
                target = self.rng.choice(self._sheriff_candidates)
            ballots[pid] = target
            self._emit_reasoning(pid, "sheriff_vote", reasoning, mode=_reason_mode(voter))
        self.state.sheriff_election = SheriffElectionState(
            candidates=self._sheriff_candidates,
            withdrawn=self._sheriff_withdrawn,
            ballots=ballots,
            is_revote=False,
        )
        self._emit(
            "vote",
            {"ballots": ballots, "type": "sheriff"},
            ["public", "observer"],
        )
        self._transition(Phase.SHERIFF_RESULT)

    async def _handle_sheriff_result(self) -> None:
        se = self.state.sheriff_election
        sheriff_id: int | None = None
        counts: dict[int, int] = {}
        if se and se.ballots:
            for target in se.ballots.values():
                counts[int(target)] = counts.get(int(target), 0) + 1
            if counts:
                max_votes = max(counts.values())
                top = [pid for pid, c in counts.items() if c == max_votes]
                if len(top) == 1:
                    sheriff_id = top[0]
                elif not se.is_revote:
                    self._sheriff_candidates = top
                    self._sheriff_speech_queue = list(top)
                    self._sheriff_speech_index = 0
                    se.is_revote = True
                    se.ballots = {}
                    self._emit(
                        "sheriff_election",
                        {"candidates": top, "is_revote": True},
                        ["public", "observer"],
                    )
                    self._transition(Phase.SHERIFF_SPEECH)
                    return
        if sheriff_id is not None:
            p = self.state.get_player(sheriff_id)
            if p:
                p.is_sheriff = True
                self.state.sheriff_id = sheriff_id
        self._emit(
            "sheriff_result",
            {"sheriff_id": sheriff_id, "votes": counts},
            ["public", "observer"],
        )
        self._post_death_phase = Phase.DISCUSS_ORDER
        self._transition(Phase.DEATH_SKILL)

    # ---- Death processing -------------------------------------------- #
    async def _handle_death_skill(self) -> None:
        """Process the death queue one death at a time, including chained
        hunter shots and sheriff transfers."""
        if not self.state.death_queue:
            self._transition(Phase.LAST_WORDS)
            return

        # Pop the first death record that hasn't been applied yet
        dr = self.state.death_queue[0]
        player = self.state.get_player(dr.player_id)
        if player is None or not player.alive:
            # Already processed or invalid — drop and continue
            self.state.death_queue.pop(0)
            return  # next step will pick up the next death

        was_sheriff = player.is_sheriff
        player.alive = False
        if was_sheriff:
            player.is_sheriff = False
            self.state.sheriff_id = None

        self._emit(
            "death",
            {
                "player_id": dr.player_id,
                "causes": [c.value for c in dr.causes],
                "timing": dr.timing,
            },
            ["public", "observer"],
        )

        # Hunter shot chain — only if the death cause permits it
        if dr.can_trigger_death_skill and player.role == RoleId.HUNTER:
            self._emit_invocation_start(player.id, "hunter_shoot")
            action, reasoning = await agent_module.agent_hunter_shoot(player, self.state)
            self._emit(
                "death_skill",
                action.to_dict(),
                ["public", "observer"],
                player_id=player.id,
            )
            self._emit_reasoning(
                player.id, "hunter_shoot", reasoning, mode=_reason_mode(player)
            )
            if action.target is not None:
                shot_dr = DeathRecord(
                    player_id=action.target,
                    timing=dr.timing,
                    round_no=dr.round_no,
                    causes=[DeathCause.HUNTER_SHOT],
                    can_trigger_death_skill=True,
                    has_last_words=dr.timing == "day",
                )
                # Append after the current entry but keep order
                self.state.death_queue.append(shot_dr)

        # Sheriff transfer
        if was_sheriff:
            self._sheriff_transfer_pid = dr.player_id
            # Don't pop yet; remember the dr so transfer phase can run, then
            # we'll continue with remaining queue.
            self.state.death_queue.pop(0)
            self._completed_deaths.append(dr)
            self._transition(Phase.SHERIFF_TRANSFER)
            return

        # Otherwise just remove from queue and continue next step
        self.state.death_queue.pop(0)
        self._completed_deaths.append(dr)
        # Stay in DEATH_SKILL — runner.run() will call us again

    async def _handle_sheriff_transfer(self) -> None:
        """Old sheriff (already dead) decides to pass the badge or destroy it."""
        prev_pid = self._sheriff_transfer_pid
        prev = self.state.get_player(prev_pid) if prev_pid is not None else None
        if prev is None:
            self._transition(Phase.DEATH_SKILL)
            return

        if prev.model_config is None:
            action = SheriffTransferAction(target="tear_badge")
            reasoning = "默认撕毁警徽。"
        else:
            self._emit_invocation_start(prev.id, "sheriff_transfer")
            action, reasoning = await agent_module.agent_sheriff_transfer(prev, self.state)
        self._emit(
            "sheriff_transfer",
            {**action.to_dict(), "from_player_id": prev.id},
            ["public", "observer"],
            player_id=prev.id,
        )
        self._emit_reasoning(
            prev.id, "sheriff_transfer", reasoning, mode=_reason_mode(prev)
        )

        if action.target == "tear_badge":
            self.state.badge_destroyed = True
        elif isinstance(action.target, int):
            new_sheriff = self.state.get_player(action.target)
            if new_sheriff and new_sheriff.alive:
                new_sheriff.is_sheriff = True
                self.state.sheriff_id = action.target

        self._sheriff_transfer_pid = None
        self._transition(Phase.DEATH_SKILL)

    async def _handle_last_words(self) -> None:
        """Each newly-dead player whose record allows last words speaks."""
        for dr in self._completed_deaths:
            if not dr.has_last_words:
                continue
            player = self.state.get_player(dr.player_id)
            if player is None:
                continue
            content = "（无遗言）"
            reasoning = "未配置模型，跳过遗言。"
            if player.model_config is not None:
                self._emit_invocation_start(player.id, "last_words")
                content, reasoning = await agent_module.agent_last_words(
                    player, self.state
                )
            self._emit(
                "last_words",
                {"player_id": dr.player_id, "content": content},
                ["public", "observer"],
                player_id=dr.player_id,
            )
            self._emit_reasoning(
                dr.player_id, "last_words", reasoning, mode=_reason_mode(player)
            )
        # Consume — last words for this batch are now done
        self._completed_deaths = []
        self._transition(Phase.WIN_CHECK)

    async def _handle_win_check(self) -> None:
        winner = check_win(self.state)
        if winner is not None:
            self._emit(
                "game_end",
                {"winner": winner.value, "round_no": self.state.round_no},
                ["public", "observer"],
            )
            self._transition(Phase.GAME_END)
            return
        # Continue to either day discussion or next night
        self._transition(self._post_death_phase)

    # ---- Day phase --------------------------------------------------- #
    async def _handle_discuss_order(self) -> None:
        alive = self._alive_ids()
        if not alive:
            self._transition(Phase.WIN_CHECK)
            return
        # Sheriff (if any) chooses direction; default: from sheriff seat or random
        if self.state.sheriff_id and self.state.sheriff_id in alive:
            start = self.state.sheriff_id
        else:
            start = self.rng.choice(alive)
        idx = alive.index(start)
        self._speech_queue = alive[idx:] + alive[:idx]
        self._speech_index = 0
        self._emit(
            "discuss_order",
            {"order": self._speech_queue, "round_no": self.state.round_no},
            ["public", "observer"],
        )
        self._transition(Phase.DISCUSS)

    async def _handle_discuss(self) -> None:
        if self._speech_index >= len(self._speech_queue):
            self._transition(Phase.VOTE)
            return
        speaker_id = self._speech_queue[self._speech_index]
        self._speech_index += 1
        player = self.state.get_player(speaker_id)
        if player is None or not player.alive:
            return  # next step
        self._emit_invocation_start(player.id, "speech")
        action, reasoning = await agent_module.agent_speech(
            player, self.state, self.state.round_no, self._build_public_log()
        )
        self._emit(
            "speech",
            action.to_dict(),
            ["public", "observer"],
            player_id=speaker_id,
        )
        self._emit_reasoning(speaker_id, "speech", reasoning, mode=_reason_mode(player))

    async def _handle_vote(self) -> None:
        alive = self._alive_ids()
        vs = VoteState(candidates=None)
        weights: dict[int, float] = {}
        for pid in alive:
            weights[pid] = 1.5 if self.state.sheriff_id == pid else 1.0
        vs.vote_weights = weights

        ballots: dict[int, int | str] = {}
        for pid in alive:
            player = self.state.get_player(pid)
            if player is None:
                continue
            self._emit_invocation_start(pid, "vote")
            action, reasoning = await agent_module.agent_vote(player, self.state, vs)
            ballots[pid] = action.target
            self._emit_reasoning(pid, "vote", reasoning, mode=_reason_mode(player))
        vs.ballots = ballots
        self.state.vote_state = vs
        self._emit(
            "vote",
            {"ballots": ballots, "type": "exile"},
            ["public", "observer"],
        )
        self._transition(Phase.VOTE_RESULT)

    async def _handle_vote_result(self) -> None:
        vs = self.state.vote_state
        if not vs:
            self._transition(Phase.NO_ELIMINATION)
            return

        counts: dict[int, float] = {}
        abstain_count = 0
        for voter, target in vs.ballots.items():
            if target == "abstain":
                abstain_count += 1
                continue
            weight = vs.vote_weights.get(voter, 1.0)
            counts[int(target)] = counts.get(int(target), 0.0) + weight

        if not counts:
            self._emit("no_elimination", {"reason": "all_abstain"}, ["public", "observer"])
            self._post_death_phase = Phase.NIGHT_BEGIN
            self._transition(Phase.WIN_CHECK)
            return

        max_votes = max(counts.values())
        top = [pid for pid, c in counts.items() if abs(c - max_votes) < 1e-9]

        if len(top) == 1:
            target = top[0]
            self._emit(
                "exile",
                {"player_id": target, "votes": counts},
                ["public", "observer"],
            )
            dr = DeathRecord(
                player_id=target,
                timing="day",
                round_no=self.state.round_no,
                causes=[DeathCause.EXILE],
                can_trigger_death_skill=True,
                has_last_words=True,
            )
            self.state.death_queue.append(dr)
            self._post_death_phase = Phase.NIGHT_BEGIN
            self._transition(Phase.EXILE)
            return

        # Tie
        if not vs.is_revote:
            vs.is_revote = True
            vs.candidates = top
            vs.excluded_voters = top
            vs.ballots = {}
            self._emit(
                "tie_vote_announce",
                {"candidates": top},
                ["public", "observer"],
            )
            self._transition(Phase.TIE_SPEECH)
        else:
            self._emit(
                "no_elimination",
                {"reason": "revote_tie", "tied": top},
                ["public", "observer"],
            )
            self._post_death_phase = Phase.NIGHT_BEGIN
            self._transition(Phase.WIN_CHECK)

    async def _handle_tie_speech(self) -> None:
        # Tie candidates each speak briefly
        vs = self.state.vote_state
        if not vs or not vs.candidates:
            self._transition(Phase.TIE_VOTE)
            return
        for pid in vs.candidates:
            player = self.state.get_player(pid)
            if player is None or not player.alive:
                continue
            self._emit_invocation_start(player.id, "tie_speech")
            action, reasoning = await agent_module.agent_speech(
                player, self.state, self.state.round_no, self._build_public_log()
            )
            self._emit(
                "speech",
                {**action.to_dict(), "context": "tie_speech"},
                ["public", "observer"],
                player_id=pid,
            )
            self._emit_reasoning(pid, "tie_speech", reasoning, mode=_reason_mode(player))
        self._transition(Phase.TIE_VOTE)

    async def _handle_tie_vote(self) -> None:
        vs = self.state.vote_state
        if not vs or not vs.candidates:
            self._transition(Phase.NO_ELIMINATION)
            return
        alive = self._alive_ids()
        voters = [pid for pid in alive if pid not in vs.excluded_voters]
        ballots: dict[int, int | str] = {}
        for pid in voters:
            player = self.state.get_player(pid)
            if player is None:
                continue
            self._emit_invocation_start(pid, "tie_vote")
            action, reasoning = await agent_module.agent_vote(player, self.state, vs)
            target = action.target
            if not isinstance(target, int) or target not in (vs.candidates or []):
                target = self.rng.choice(vs.candidates)
            ballots[pid] = target
            self._emit_reasoning(pid, "tie_vote", reasoning, mode=_reason_mode(player))
        vs.ballots = ballots
        self._emit(
            "vote",
            {"ballots": ballots, "type": "tie_revote"},
            ["public", "observer"],
        )
        self._transition(Phase.VOTE_RESULT)

    async def _handle_exile(self) -> None:
        # Move to death-skill processing for the exile victim. The day
        # exile death record is already appended in _handle_vote_result.
        self._transition(Phase.DEATH_SKILL)

    async def _handle_no_elimination(self) -> None:
        self._post_death_phase = Phase.NIGHT_BEGIN
        self._transition(Phase.WIN_CHECK)

    async def _handle_self_destruct(self) -> None:
        # MVP: self-destruct path is unused; treat as DAY_ABORTED
        self._transition(Phase.DAY_ABORTED)

    async def _handle_day_aborted(self) -> None:
        self._post_death_phase = Phase.NIGHT_BEGIN
        self._transition(Phase.WIN_CHECK)

    async def _handle_game_end(self) -> None:
        pass


def _reason_mode(player: Player | None) -> str:
    """Return the reasoning trace mode for a player based on their model.

    For thinking-mode capable models we mark the trace as ``full``;
    otherwise we keep the previous ``self_explanation`` label.
    """
    if player is None or player.model_config is None:
        return "self_explanation"
    mid = getattr(player.model_config, "model_id", "") or ""
    if mid in {"deepseek-v4-flash", "deepseek-v4-pro", "deepseek-reasoner"}:
        return "full"
    return "self_explanation"
