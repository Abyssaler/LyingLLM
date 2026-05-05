"""Game state and phase models."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

from lyingllm.domain.models.player import Player


class Phase(str, Enum):
    """All phases in the fixed state machine."""

    SETUP = "setup"
    ROLE_ASSIGNMENT = "role_assignment"
    NIGHT_BEGIN = "night_begin"
    GUARD_ACTION = "guard_action"
    WOLF_DISCUSS = "wolf_discuss"
    WITCH_ACTION = "witch_action"
    SEER_ACTION = "seer_action"
    NIGHT_RESOLVE = "night_resolve"
    DAWN = "dawn"
    FIRST_DAY_SHERIFF_GATE = "first_day_sheriff_gate"
    SHERIFF_ELECTION = "sheriff_election"
    SHERIFF_SPEECH = "sheriff_speech"
    SHERIFF_VOTE = "sheriff_vote"
    SHERIFF_RESULT = "sheriff_result"
    DEATH_SKILL = "death_skill"
    SHERIFF_TRANSFER = "sheriff_transfer"
    LAST_WORDS = "last_words"
    WIN_CHECK = "win_check"
    DISCUSS_ORDER = "discuss_order"
    DISCUSS = "discuss"
    VOTE = "vote"
    VOTE_RESULT = "vote_result"
    TIE_SPEECH = "tie_speech"
    TIE_VOTE = "tie_vote"
    EXILE = "exile"
    NO_ELIMINATION = "no_elimination"
    SELF_DESTRUCT = "self_destruct"
    DAY_ABORTED = "day_aborted"
    GAME_END = "game_end"


class NightActionSet:
    """All actions submitted during a single night.

    ``wolf_kill_target`` is required (system will fill a default if needed).
    """

    def __init__(
        self,
        *,
        round_no: int,
        guard_target: int | None = None,
        wolf_kill_target: int | None = None,
        witch_save_used: bool = False,
        witch_poison_target: int | None = None,
        seer_check_target: int | None = None,
    ) -> None:
        self.round_no = round_no
        self.guard_target = guard_target
        self.wolf_kill_target = wolf_kill_target
        self.witch_save_used = witch_save_used
        self.witch_poison_target = witch_poison_target
        self.seer_check_target = seer_check_target


class VoteState:
    """Daytime exile vote state."""

    def __init__(
        self,
        *,
        candidates: list[int] | None = None,
        excluded_voters: list[int] | None = None,
        ballots: dict[int, int | str] | None = None,
        vote_weights: dict[int, float] | None = None,
        is_revote: bool = False,
    ) -> None:
        self.candidates = candidates  # None = any alive player
        self.excluded_voters = excluded_voters or []
        self.ballots: dict[int, int | str] = ballots or {}  # target id or "abstain"
        self.vote_weights = vote_weights or {}
        self.is_revote = is_revote


class SheriffElectionState:
    """Sheriff election state (day 1 only)."""

    def __init__(
        self,
        *,
        candidates: list[int] | None = None,
        withdrawn: list[int] | None = None,
        ballots: dict[int, int] | None = None,
        is_revote: bool = False,
    ) -> None:
        self.candidates = candidates or []
        self.withdrawn = withdrawn or []
        self.ballots: dict[int, int] = ballots or {}
        self.is_revote = is_revote


class DeathCause(str, Enum):
    WOLF_KILL = "wolf_kill"
    GUARD_AND_SAVE = "guard_and_save"
    WITCH_POISON = "witch_poison"
    HUNTER_SHOT = "hunter_shot"
    WHITE_WOLF_KING_TAKE = "white_wolf_king_take"
    EXILE = "exile"
    SELF_DESTRUCT = "self_destruct"


class DeathRecord:
    """A pending or processed death entry."""

    def __init__(
        self,
        *,
        player_id: int,
        timing: str,  # "night" or "day"
        round_no: int,
        causes: list[DeathCause],
        can_trigger_death_skill: bool = True,
        has_last_words: bool = False,
    ) -> None:
        self.player_id = player_id
        self.timing = timing
        self.round_no = round_no
        self.causes = causes
        self.can_trigger_death_skill = can_trigger_death_skill
        self.has_last_words = has_last_words


class GameState:
    """The single source of truth for game state.

    Only the engine mutates this object.
    """

    def __init__(
        self,
        *,
        game_id: str,
        phase: Phase = Phase.SETUP,
        round_no: int = 0,
        players: list[Player] | None = None,
        sheriff_id: int | None = None,
        badge_destroyed: bool = False,
        night_actions: NightActionSet | None = None,
        vote_state: VoteState | None = None,
        sheriff_election: SheriffElectionState | None = None,
        death_queue: list[DeathRecord] | None = None,
        public_memory: list[int] | None = None,
        private_memory: dict[int, list[int]] | None = None,
        wolf_memory: list[int] | None = None,
    ) -> None:
        self.game_id = game_id
        self.phase = phase
        self.round_no = round_no
        self.players: list[Player] = players or []
        self.sheriff_id = sheriff_id
        self.badge_destroyed = badge_destroyed
        self.night_actions = night_actions
        self.vote_state = vote_state
        self.sheriff_election = sheriff_election
        self.death_queue: list[DeathRecord] = death_queue or []
        self.public_memory: list[int] = public_memory or []
        self.private_memory: dict[int, list[int]] = private_memory or {}
        self.wolf_memory: list[int] = wolf_memory or []

    @property
    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    @property
    def alive_wolves(self) -> int:
        """Count werewolf + white_wolf_king (rule.md §1.2)."""
        return sum(
            1
            for p in self.players
            if p.alive and p.role in ("werewolf", "white_wolf_king")
        )

    @property
    def alive_gods(self) -> int:
        return sum(1 for p in self.players if p.alive and p.role_group.value == "god")

    @property
    def alive_villagers(self) -> int:
        return sum(
            1 for p in self.players if p.alive and p.role_group.value == "villager"
        )

    @property
    def is_first_night(self) -> bool:
        return self.round_no == 1

    def get_player(self, player_id: int) -> Player | None:
        for p in self.players:
            if p.id == player_id:
                return p
        return None


class PlayerSetupConfig:
    def __init__(
        self,
        *,
        player_id: int,
        display_name: str | None = None,
        model_config: Any | None = None,
    ) -> None:
        self.player_id = player_id
        self.display_name = display_name
        self.model_config = model_config


class RuntimeConfig:
    def __init__(
        self,
        *,
        max_output_tokens: int = 2000,
        timeout_seconds: int = 30,
        retry_limit: int = 2,
    ) -> None:
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.retry_limit = retry_limit


class GameSetupConfig:
    def __init__(
        self,
        *,
        players: list[PlayerSetupConfig],
        runtime: RuntimeConfig | None = None,
    ) -> None:
        if len(players) != 12:
            raise ValueError("Exactly 12 players required")
        seen = set()
        for ps in players:
            if ps.player_id in seen:
                raise ValueError(f"Duplicate player_id {ps.player_id}")
            if not (1 <= ps.player_id <= 12):
                raise ValueError("player_id must be 1..12")
            seen.add(ps.player_id)
        self.players = players
        self.runtime = runtime or RuntimeConfig()
