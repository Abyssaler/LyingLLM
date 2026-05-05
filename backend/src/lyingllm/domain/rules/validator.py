"""Action validators.

Every action produced by an agent must pass validation before the engine
applies it.  Validation is stateful: it depends on the current ``GameState``
and, for night actions, the partially-built ``NightActionSet``.
"""

from __future__ import annotations

import random
from typing import Any

from lyingllm.domain.models.player import Player, RoleId
from lyingllm.domain.models.game import (
    GameState,
    NightActionSet,
    VoteState,
    SheriffElectionState,
)
from lyingllm.domain.models.action import (
    GuardAction,
    WolfVoteKillAction,
    WitchAction,
    SeerAction,
    VoteAction,
    HunterShootAction,
    SheriffTransferAction,
    SelfDestructAction,
)
from lyingllm.domain.rules import constants as C


def _alive_ids(state: GameState) -> set[int]:
    return {p.id for p in state.players if p.alive}


def _alive_village_ids(state: GameState) -> set[int]:
    return {p.id for p in state.players if p.alive and p.faction.value == "village"}


class ValidationResult:
    def __init__(self, ok: bool, message: str = "") -> None:
        self.ok = ok
        self.message = message

    def __bool__(self) -> bool:
        return self.ok


# --------------------------------------------------------------------------- #
# Guard
# --------------------------------------------------------------------------- #
def validate_guard(
    action: GuardAction,
    player: Player,
    state: GameState,
) -> ValidationResult:
    if action.target is None:
        # skip guard is always legal
        return ValidationResult(True)
    if action.target not in _alive_ids(state):
        return ValidationResult(False, "Guard target must be an alive player")
    if (
        C.GUARD_CANNOT_GUARD_SAME_PLAYER_CONSECUTIVELY
        and player.last_guard_target == action.target
    ):
        return ValidationResult(
            False, "Cannot guard the same player on consecutive nights"
        )
    return ValidationResult(True)


def default_guard(player: Player, state: GameState) -> GuardAction:
    """Default: skip guard."""
    return GuardAction(target=None)


# --------------------------------------------------------------------------- #
# Wolf kill vote
# --------------------------------------------------------------------------- #
def validate_wolf_vote_kill(
    action: WolfVoteKillAction,
    player: Player,
    state: GameState,
) -> ValidationResult:
    if action.target not in _alive_ids(state):
        return ValidationResult(False, "Kill target must be alive")
    # Wolves normally only kill village-faction players
    target_player = state.get_player(action.target)
    assert target_player is not None
    if target_player.faction.value == "wolf":
        return ValidationResult(False, "Wolves cannot target a wolf-faction player")
    return ValidationResult(True)


def default_wolf_vote_kill(
    player: Player, state: GameState
) -> WolfVoteKillAction:
    """Default: random alive village-faction player."""
    targets = list(_alive_village_ids(state))
    if not targets:
        # edge case — should not happen in a normal game
        targets = list(_alive_ids(state))
    target = random.choice(targets)
    return WolfVoteKillAction(target=target, reason="default action")


# --------------------------------------------------------------------------- #
# Witch
# --------------------------------------------------------------------------- #
def validate_witch(
    action: WitchAction,
    player: Player,
    state: GameState,
    night_actions: NightActionSet,
) -> ValidationResult:
    # Cannot use both potions same night
    if (
        C.WITCH_CANNOT_USE_BOTH_POTIONS_SAME_NIGHT
        and action.use_save
        and action.poison_target is not None
    ):
        return ValidationResult(
            False, "Cannot use both save and poison on the same night"
        )
    # Save must target the wolf kill target, and only if unused
    if action.use_save and player.witch_save_used:
        return ValidationResult(False, "Save potion already used")
    if action.poison_target is not None:
        if player.witch_poison_used:
            return ValidationResult(False, "Poison potion already used")
        if action.poison_target not in _alive_ids(state):
            return ValidationResult(
                False, "Poison target must be an alive player"
            )
    return ValidationResult(True)


def default_witch(
    player: Player, state: GameState, night_actions: NightActionSet
) -> WitchAction:
    return WitchAction(use_save=False, poison_target=None)


# --------------------------------------------------------------------------- #
# Seer
# --------------------------------------------------------------------------- #
def validate_seer(
    action: SeerAction,
    player: Player,
    state: GameState,
) -> ValidationResult:
    if action.target == player.id:
        return ValidationResult(False, "Seer cannot check themselves")
    if action.target not in _alive_ids(state):
        return ValidationResult(
            False, "Seer target must be an alive player"
        )
    if action.target in player.checked_players:
        return ValidationResult(
            False, "Seer cannot check a player already checked"
        )
    return ValidationResult(True)


def default_seer(player: Player, state: GameState) -> SeerAction:
    """Default: random alive player not yet checked (excluding self)."""
    candidates = [
        p.id
        for p in state.players
        if p.alive and p.id != player.id and p.id not in player.checked_players
    ]
    if not candidates:
        candidates = [p.id for p in state.players if p.alive and p.id != player.id]
    target = random.choice(candidates) if candidates else player.id
    return SeerAction(target=target)


# --------------------------------------------------------------------------- #
# Vote (day exile)
# --------------------------------------------------------------------------- #
def validate_vote(
    action: VoteAction,
    player: Player,
    state: GameState,
    vote_state: VoteState,
) -> ValidationResult:
    if isinstance(action.target, str) and action.target == "abstain":
        return ValidationResult(True)
    if not isinstance(action.target, int):
        return ValidationResult(False, "Vote target must be a player id or 'abstain'")
    if action.target not in _alive_ids(state):
        return ValidationResult(False, "Vote target must be alive")
    if vote_state.excluded_voters and player.id in vote_state.excluded_voters:
        return ValidationResult(False, "Tie candidates cannot vote")
    if vote_state.candidates is not None and action.target not in vote_state.candidates:
        return ValidationResult(
            False, "Must vote for one of the tie candidates"
        )
    return ValidationResult(True)


def default_vote(
    player: Player, state: GameState, vote_state: VoteState
) -> VoteAction:
    return VoteAction(target="abstain")


# --------------------------------------------------------------------------- #
# Hunter shoot
# --------------------------------------------------------------------------- #
def validate_hunter_shoot(
    action: HunterShootAction,
    player: Player,
    state: GameState,
) -> ValidationResult:
    if not player.can_shoot:
        return ValidationResult(False, "Hunter cannot shoot in this situation")
    if action.target is None:
        return ValidationResult(True)  # choose not to shoot
    if action.target not in _alive_ids(state):
        return ValidationResult(False, "Shoot target must be alive")
    return ValidationResult(True)


def default_hunter_shoot(
    player: Player, state: GameState
) -> HunterShootAction:
    return HunterShootAction(target=None)


# --------------------------------------------------------------------------- #
# Sheriff transfer
# --------------------------------------------------------------------------- #
def validate_sheriff_transfer(
    action: SheriffTransferAction,
    player: Player,
    state: GameState,
) -> ValidationResult:
    if isinstance(action.target, str) and action.target == "tear_badge":
        return ValidationResult(True)
    if isinstance(action.target, int):
        if action.target not in _alive_ids(state):
            return ValidationResult(
                False, "Transfer target must be alive"
            )
        return ValidationResult(True)
    return ValidationResult(
        False, "Sheriff transfer target must be an alive player or 'tear_badge'"
    )


def default_sheriff_transfer(
    player: Player, state: GameState
) -> SheriffTransferAction:
    return SheriffTransferAction(target="tear_badge")


# --------------------------------------------------------------------------- #
# Self destruct
# --------------------------------------------------------------------------- #
def validate_self_destruct(
    action: SelfDestructAction,
    player: Player,
    state: GameState,
) -> ValidationResult:
    if player.role == RoleId.WEREWOLF:
        if action.target is not None:
            return ValidationResult(
                False, "Normal werewolf self-destruct cannot take a target"
            )
        return ValidationResult(True)
    if player.role == RoleId.WHITE_WOLF_KING:
        if action.target is None:
            return ValidationResult(
                False, "White wolf king self-destruct must target an alive player"
            )
        if action.target not in _alive_ids(state):
            return ValidationResult(
                False, "Self-destruct target must be alive"
            )
        return ValidationResult(True)
    return ValidationResult(False, "Only werewolf faction can self-destruct")


def default_self_destruct(
    player: Player, state: GameState
) -> SelfDestructAction:
    # This should never be used as a default — self-destruct is optional
    return SelfDestructAction(target=None)
