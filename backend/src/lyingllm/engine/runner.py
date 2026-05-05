"""Game runner — the only module that mutates GameState.

Drives the fixed state machine from ``SETUP`` to ``GAME_END``.
Each phase handler may invoke stub agents, validate actions, emit events,
and transition to the next phase.
"""

from __future__ import annotations

import random
from typing import Callable

from lyingllm.domain.models.player import Player, RoleId, Faction
from lyingllm.domain.models.game import (
    GameState,
    Phase,
    NightActionSet,
    VoteState,
    SheriffElectionState,
    DeathRecord,
    DeathCause,
    GameSetupConfig,
)
from lyingllm.domain.models.event import GameEvent
from lyingllm.domain.models.action import (
    GuardAction,
    WolfVoteKillAction,
    WitchAction,
    SeerAction,
    SpeechAction,
    VoteAction,
    HunterShootAction,
    SheriffTransferAction,
    SelfDestructAction,
)
from lyingllm.domain.rules.roles import assign_roles
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
    validate_self_destruct,
)
from lyingllm.engine.resolver import resolve_night, check_win
from lyingllm.storage.event_log import EventLog


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
        self._handlers: dict[Phase, Callable[[], None]] = {
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
        self._death_queue_index: int = 0
        self._sheriff_candidates: list[int] = []
        self._sheriff_withdrawn: list[int] = []
        self._vote_tie_candidates: list[int] = []
        self._current_exile_target: int | None = None

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def step(self) -> bool:
        """Advance one phase.  Returns ``True`` when the game has ended."""
        if self.state.phase == Phase.GAME_END:
            return True
        handler = self._handlers[self.state.phase]
        handler()
        return self.state.phase == Phase.GAME_END

    def run(self) -> None:
        while not self.step():
            pass

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
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

    def _alive_ids(self) -> set[int]:
        return {p.id for p in self.state.players if p.alive}

    def _find_player(self, role: RoleId) -> Player | None:
        for p in self.state.players:
            if p.role == role and p.alive:
                return p
        return None

    def _find_players(self, *roles: RoleId) -> list[Player]:
        return [p for p in self.state.players if p.role in roles and p.alive]

    # --------------------------------------------------------------------- #
    # Phase handlers
    # --------------------------------------------------------------------- #
    def _handle_setup(self) -> None:
        self._transition(Phase.ROLE_ASSIGNMENT)

    def _handle_role_assignment(self) -> None:
        roles = assign_roles(rng=self.rng)
        players = []
        for i, role in enumerate(roles):
            pid = i + 1
            setup = next(
                (s for s in self.setup.players if s.player_id == pid), None
            )
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

    def _handle_night_begin(self) -> None:
        self.state.round_no += 1
        self.state.night_actions = NightActionSet(round_no=self.state.round_no)
        self._transition(Phase.GUARD_ACTION)

    def _handle_guard_action(self) -> None:
        guard = self._find_player(RoleId.GUARD)
        if guard is None:
            action = default_guard(guard, self.state) if guard else GuardAction(target=None)
        else:
            action = default_guard(guard, self.state)
        self.state.night_actions.guard_target = action.target
        if guard:
            guard.last_guard_target = action.target
        self._emit("night_action", action.to_dict(), ["observer"], player_id=guard.id if guard else None)
        self._transition(Phase.WOLF_DISCUSS)

    def _handle_wolf_discuss(self) -> None:
        wolves = self._find_players(RoleId.WEREWOLF, RoleId.WHITE_WOLF_KING)
        if not wolves:
            # Fallback — shouldn't happen in normal game
            self.state.night_actions.wolf_kill_target = next(iter(self._alive_ids()))
        else:
            action = default_wolf_vote_kill(wolves[0], self.state)
            self.state.night_actions.wolf_kill_target = action.target
            self._emit(
                "night_action",
                action.to_dict(),
                ["wolves", "observer"],
            )
        self._transition(Phase.WITCH_ACTION)

    def _handle_witch_action(self) -> None:
        witch = self._find_player(RoleId.WITCH)
        if witch is None:
            action = WitchAction(use_save=False, poison_target=None)
        else:
            action = default_witch(witch, self.state, self.state.night_actions)
            if action.use_save:
                witch.witch_save_used = True
            if action.poison_target is not None:
                witch.witch_poison_used = True
        self.state.night_actions.witch_save_used = action.use_save
        self.state.night_actions.witch_poison_target = action.poison_target
        self._emit("night_action", action.to_dict(), ["observer"], player_id=witch.id if witch else None)
        self._transition(Phase.SEER_ACTION)

    def _handle_seer_action(self) -> None:
        seer = self._find_player(RoleId.SEER)
        if seer is None:
            action = default_seer(seer, self.state) if seer else SeerAction(target=1)
        else:
            action = default_seer(seer, self.state)
            seer.checked_players.add(action.target)
        self.state.night_actions.seer_check_target = action.target
        self._emit("night_action", action.to_dict(), ["observer"], player_id=seer.id if seer else None)
        self._transition(Phase.NIGHT_RESOLVE)

    def _handle_night_resolve(self) -> None:
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

    def _handle_dawn(self) -> None:
        deaths = self.state.death_queue
        dead_ids = [d.player_id for d in deaths]
        self._emit(
            "dawn",
            {"dead_players": dead_ids},
            ["public", "observer"],
        )
        if self.state.is_first_night:
            self._transition(Phase.FIRST_DAY_SHERIFF_GATE)
        else:
            self._transition(Phase.DEATH_SKILL)

    def _handle_first_day_sheriff_gate(self) -> None:
        self._transition(Phase.SHERIFF_ELECTION)

    def _handle_sheriff_election(self) -> None:
        alive = [p.id for p in self.state.players if p.alive]
        # Stub: first 3 wolves run for sheriff, plus 1 random villager
        wolves = [p.id for p in self.state.players if p.alive and p.faction == Faction.WOLF]
        villagers = [p.id for p in self.state.players if p.alive and p.faction == Faction.VILLAGE]
        candidates = wolves[:3]
        if villagers and len(candidates) < 4:
            candidates.append(self.rng.choice(villagers))
        self._sheriff_candidates = candidates
        self._sheriff_withdrawn = []
        self._emit(
            "sheriff_election",
            {"candidates": candidates},
            ["public", "observer"],
        )
        self._transition(Phase.SHERIFF_SPEECH)

    def _handle_sheriff_speech(self) -> None:
        # Stub: no speeches, no self-destruct in MVP
        self._transition(Phase.SHERIFF_VOTE)

    def _handle_sheriff_vote(self) -> None:
        alive = [p.id for p in self.state.players if p.alive]
        voters = [pid for pid in alive if pid not in self._sheriff_candidates]
        ballots: dict[int, int] = {}
        for v in voters:
            if self._sheriff_candidates:
                ballots[v] = self.rng.choice(self._sheriff_candidates)
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

    def _handle_sheriff_result(self) -> None:
        se = self.state.sheriff_election
        if not se or not se.ballots:
            self._emit("sheriff_result", {"sheriff_id": None}, ["public", "observer"])
            self._transition(Phase.DEATH_SKILL)
            return

        counts: dict[int, int] = {}
        for target in se.ballots.values():
            counts[target] = counts.get(target, 0) + 1
        max_votes = max(counts.values()) if counts else 0
        top = [pid for pid, c in counts.items() if c == max_votes]

        if len(top) == 1:
            winner = top[0]
            self.state.sheriff_id = winner
            p = self.state.get_player(winner)
            if p:
                p.is_sheriff = True
            self._emit(
                "sheriff_result",
                {"sheriff_id": winner, "votes": counts},
                ["public", "observer"],
            )
            self._transition(Phase.DEATH_SKILL)
        else:
            # Revote once
            if not se.is_revote:
                self._sheriff_candidates = top
                se.is_revote = True
                se.ballots = {}
                self._transition(Phase.SHERIFF_SPEECH)
            else:
                self._emit(
                    "sheriff_result",
                    {"sheriff_id": None, "votes": counts},
                    ["public", "observer"],
                )
                self._transition(Phase.DEATH_SKILL)

    def _handle_death_skill(self) -> None:
        # Process death queue from current index
        while self._death_queue_index < len(self.state.death_queue):
            dr = self.state.death_queue[self._death_queue_index]
            player = self.state.get_player(dr.player_id)
            self._death_queue_index += 1

            if player and player.alive:
                player.alive = False
                # Remove sheriff badge if applicable
                if player.is_sheriff:
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

                if dr.can_trigger_death_skill and player.role == RoleId.HUNTER:
                    action = default_hunter_shoot(player, self.state)
                    self._emit(
                        "death_skill",
                        action.to_dict(),
                        ["public", "observer"],
                        player_id=player.id,
                    )
                    if action.target is not None:
                        # Hunter shot creates a new death
                        shot_dr = DeathRecord(
                            player_id=action.target,
                            timing=dr.timing,
                            round_no=dr.round_no,
                            causes=[DeathCause.HUNTER_SHOT],
                            can_trigger_death_skill=True,
                            has_last_words=dr.timing == "day",
                        )
                        self.state.death_queue.append(shot_dr)

                if player.id == self.state.sheriff_id:
                    self._transition(Phase.SHERIFF_TRANSFER)
                    return

        # No more deaths to process
        if self.state.phase == Phase.DEATH_SKILL:
            self._transition(Phase.LAST_WORDS)

    def _handle_sheriff_transfer(self) -> None:
        # After processing a death that was the sheriff, decide transfer
        # For stub: always tear badge
        self._emit(
            "sheriff_transfer",
            {"target": "tear_badge"},
            ["public", "observer"],
        )
        self.state.badge_destroyed = True
        self._transition(Phase.DEATH_SKILL)

    def _handle_last_words(self) -> None:
        for dr in self.state.death_queue:
            if dr.has_last_words and not dr.player_id:
                continue
            player = self.state.get_player(dr.player_id)
            if player is not None:
                self._emit(
                    "last_words",
                    {"player_id": dr.player_id, "content": ""},
                    ["public", "observer"],
                    player_id=dr.player_id,
                )
        self._transition(Phase.WIN_CHECK)

    def _handle_win_check(self) -> None:
        winner = check_win(self.state)
        if winner is not None:
            self._emit(
                "game_end",
                {"winner": winner.value},
                ["public", "observer"],
            )
            self._transition(Phase.GAME_END)
        else:
            # Determine next phase
            prev = self.events.all_events()[-2].phase if len(self.events.all_events()) > 1 else Phase.SETUP
            if prev in (Phase.DAWN, Phase.DAY_ABORTED):
                # After night or day abort -> day discussion
                self._transition(Phase.DISCUSS_ORDER)
            elif prev in (Phase.LAST_WORDS, Phase.NO_ELIMINATION, Phase.EXILE):
                # After day processing -> next night
                self._transition(Phase.NIGHT_BEGIN)
            else:
                # Fallback
                self._transition(Phase.DISCUSS_ORDER)

    def _handle_discuss_order(self) -> None:
        alive = [p.id for p in self.state.players if p.alive]
        if not alive:
            self._transition(Phase.WIN_CHECK)
            return
        # Stub: random order starting from random player
        start = self.rng.choice(alive)
        idx = alive.index(start)
        self._speech_queue = alive[idx:] + alive[:idx]
        self._speech_index = 0
        self._emit(
            "discuss_order",
            {"order": self._speech_queue},
            ["public", "observer"],
        )
        self._transition(Phase.DISCUSS)

    def _handle_discuss(self) -> None:
        while self._speech_index < len(self._speech_queue):
            speaker_id = self._speech_queue[self._speech_index]
            self._speech_index += 1
            player = self.state.get_player(speaker_id)
            if player and player.alive:
                action = SpeechAction(content="")
                self._emit(
                    "speech",
                    action.to_dict(),
                    ["public", "observer"],
                    player_id=speaker_id,
                )
                # Check self-destruct (stub: never happens)
                break
        else:
            # All speeches done
            self._transition(Phase.VOTE)

    def _handle_vote(self) -> None:
        alive = [p.id for p in self.state.players if p.alive]
        vs = VoteState(candidates=None)
        weights: dict[int, float] = {}
        for pid in alive:
            weights[pid] = 1.5 if self.state.sheriff_id == pid else 1.0
        vs.vote_weights = weights

        ballots: dict[int, int | str] = {}
        for pid in alive:
            # Stub: random vote for another alive player
            targets = [p for p in alive if p != pid]
            if targets:
                ballots[pid] = self.rng.choice(targets)
            else:
                ballots[pid] = "abstain"
        vs.ballots = ballots
        self.state.vote_state = vs

        self._emit(
            "vote",
            {"ballots": ballots, "type": "exile"},
            ["public", "observer"],
        )
        self._transition(Phase.VOTE_RESULT)

    def _handle_vote_result(self) -> None:
        vs = self.state.vote_state
        if not vs:
            self._transition(Phase.NO_ELIMINATION)
            return

        # Count weighted votes
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
            self._transition(Phase.NO_ELIMINATION)
            return

        max_votes = max(counts.values())
        top = [pid for pid, c in counts.items() if abs(c - max_votes) < 1e-9]

        if len(top) == 1:
            target = top[0]
            self._current_exile_target = target
            self._emit(
                "exile",
                {"player_id": target, "votes": counts},
                ["public", "observer"],
            )
            # Create day death record
            dr = DeathRecord(
                player_id=target,
                timing="day",
                round_no=self.state.round_no,
                causes=[DeathCause.EXILE],
                can_trigger_death_skill=True,
                has_last_words=True,
            )
            self.state.death_queue.append(dr)
            self._transition(Phase.EXILE)
        else:
            # Tie
            if not vs.is_revote:
                self._vote_tie_candidates = top
                vs.is_revote = True
                vs.candidates = top
                vs.excluded_voters = top
                vs.ballots = {}
                self._transition(Phase.TIE_SPEECH)
            else:
                self._emit(
                    "no_elimination",
                    {"reason": "revote_tie", "tied": top},
                    ["public", "observer"],
                )
                self._transition(Phase.NO_ELIMINATION)

    def _handle_tie_speech(self) -> None:
        # Stub: no speeches
        self._transition(Phase.TIE_VOTE)

    def _handle_tie_vote(self) -> None:
        vs = self.state.vote_state
        if not vs or not vs.candidates:
            self._transition(Phase.NO_ELIMINATION)
            return
        alive = [p.id for p in self.state.players if p.alive]
        voters = [pid for pid in alive if pid not in vs.excluded_voters]
        ballots: dict[int, int | str] = {}
        for pid in voters:
            targets = [c for c in vs.candidates if c != pid]
            if targets:
                ballots[pid] = self.rng.choice(targets)
            else:
                ballots[pid] = "abstain"
        vs.ballots = ballots
        self._emit(
            "tie_vote",
            {"ballots": ballots},
            ["public", "observer"],
        )
        self._transition(Phase.VOTE_RESULT)

    def _handle_exile(self) -> None:
        self._death_queue_index = len(self.state.death_queue) - 1  # process only the new exile death
        self._transition(Phase.DEATH_SKILL)

    def _handle_no_elimination(self) -> None:
        self._transition(Phase.DEATH_SKILL)

    def _handle_self_destruct(self) -> None:
        # Stub: not used in MVP
        self._transition(Phase.DEATH_SKILL)

    def _handle_day_aborted(self) -> None:
        self._transition(Phase.WIN_CHECK)

    def _handle_game_end(self) -> None:
        pass
