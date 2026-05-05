"""Tests for action validators and default actions."""

import random

import pytest

from lyingllm.domain.models.player import Player, RoleId
from lyingllm.domain.models.game import GameState, NightActionSet, VoteState
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


@pytest.fixture
def base_state():
    return GameState(
        game_id="test",
        players=[
            Player(id=1, role=RoleId.GUARD),
            Player(id=2, role=RoleId.WEREWOLF),
            Player(id=3, role=RoleId.VILLAGER),
            Player(id=4, role=RoleId.WITCH),
            Player(id=5, role=RoleId.SEER),
            Player(id=6, role=RoleId.HUNTER),
            Player(id=7, role=RoleId.WHITE_WOLF_KING),
            Player(id=8, role=RoleId.VILLAGER),
            Player(id=9, role=RoleId.VILLAGER),
            Player(id=10, role=RoleId.VILLAGER),
            Player(id=11, role=RoleId.WEREWOLF),
            Player(id=12, role=RoleId.WEREWOLF),
        ],
    )


class TestGuardValidator:
    def test_skip_guard_is_valid(self, base_state):
        p = base_state.get_player(1)
        assert validate_guard(GuardAction(target=None), p, base_state).ok

    def test_guard_alive_target(self, base_state):
        p = base_state.get_player(1)
        assert validate_guard(GuardAction(target=3), p, base_state).ok

    def test_guard_consecutive_night_blocked(self, base_state):
        p = base_state.get_player(1)
        p.last_guard_target = 3
        assert not validate_guard(GuardAction(target=3), p, base_state).ok

    def test_default_guard_is_skip(self, base_state):
        p = base_state.get_player(1)
        action = default_guard(p, base_state)
        assert action.target is None


class TestWolfKillValidator:
    def test_target_villager_is_valid(self, base_state):
        p = base_state.get_player(2)
        assert validate_wolf_vote_kill(WolfVoteKillAction(target=3), p, base_state).ok

    def test_target_wolf_is_invalid(self, base_state):
        p = base_state.get_player(2)
        assert not validate_wolf_vote_kill(
            WolfVoteKillAction(target=7), p, base_state
        ).ok

    def test_default_targets_village(self, base_state):
        p = base_state.get_player(2)
        action = default_wolf_vote_kill(p, base_state)
        target = base_state.get_player(action.target)
        assert target is not None
        assert target.faction.value == "village"


class TestWitchValidator:
    def test_use_save_only(self, base_state):
        p = base_state.get_player(4)
        na = NightActionSet(round_no=1, wolf_kill_target=3)
        assert validate_witch(
            WitchAction(use_save=True, poison_target=None), p, base_state, na
        ).ok

    def test_both_potions_blocked(self, base_state):
        p = base_state.get_player(4)
        na = NightActionSet(round_no=1, wolf_kill_target=3)
        assert not validate_witch(
            WitchAction(use_save=True, poison_target=3), p, base_state, na
        ).ok

    def test_poison_used_cannot_reuse(self, base_state):
        p = base_state.get_player(4)
        p.witch_poison_used = True
        na = NightActionSet(round_no=1)
        assert not validate_witch(
            WitchAction(poison_target=3), p, base_state, na
        ).ok

    def test_default_is_no_action(self, base_state):
        p = base_state.get_player(4)
        na = NightActionSet(round_no=1)
        action = default_witch(p, base_state, na)
        assert action.use_save is False and action.poison_target is None


class TestSeerValidator:
    def test_check_other_alive(self, base_state):
        p = base_state.get_player(5)
        assert validate_seer(SeerAction(target=3), p, base_state).ok

    def test_cannot_check_self(self, base_state):
        p = base_state.get_player(5)
        assert not validate_seer(SeerAction(target=5), p, base_state).ok

    def test_cannot_check_checked(self, base_state):
        p = base_state.get_player(5)
        p.checked_players.add(3)
        assert not validate_seer(SeerAction(target=3), p, base_state).ok

    def test_default_excludes_self_and_checked(self, base_state):
        p = base_state.get_player(5)
        p.checked_players.add(3)
        action = default_seer(p, base_state)
        assert action.target != 5
        assert action.target not in p.checked_players


class TestVoteValidator:
    def test_abstain(self, base_state):
        p = base_state.get_player(3)
        vs = VoteState()
        assert validate_vote(VoteAction(target="abstain"), p, base_state, vs).ok

    def test_target_alive(self, base_state):
        p = base_state.get_player(3)
        vs = VoteState()
        assert validate_vote(VoteAction(target=1), p, base_state, vs).ok

    def test_revote_restricted(self, base_state):
        p = base_state.get_player(3)
        vs = VoteState(candidates=[1, 2], excluded_voters=[3, 4])
        assert not validate_vote(VoteAction(target=1), p, base_state, vs).ok

    def test_default_is_abstain(self, base_state):
        p = base_state.get_player(3)
        vs = VoteState()
        action = default_vote(p, base_state, vs)
        assert action.target == "abstain"


class TestHunterShootValidator:
    def test_can_shoot(self, base_state):
        p = base_state.get_player(6)
        assert validate_hunter_shoot(HunterShootAction(target=3), p, base_state).ok

    def test_cannot_shoot_when_poisoned(self, base_state):
        p = base_state.get_player(6)
        p.can_shoot = False
        assert not validate_hunter_shoot(
            HunterShootAction(target=3), p, base_state
        ).ok

    def test_default_no_shot(self, base_state):
        p = base_state.get_player(6)
        action = default_hunter_shoot(p, base_state)
        assert action.target is None


class TestSheriffTransferValidator:
    def test_transfer_to_alive(self, base_state):
        p = base_state.get_player(1)
        assert validate_sheriff_transfer(
            SheriffTransferAction(target=3), p, base_state
        ).ok

    def test_tear_badge(self, base_state):
        p = base_state.get_player(1)
        assert validate_sheriff_transfer(
            SheriffTransferAction(target="tear_badge"), p, base_state
        ).ok

    def test_default_is_tear_badge(self, base_state):
        p = base_state.get_player(1)
        action = default_sheriff_transfer(p, base_state)
        assert action.target == "tear_badge"


class TestSelfDestructValidator:
    def test_normal_werewolf_no_target(self, base_state):
        p = base_state.get_player(2)
        assert validate_self_destruct(
            SelfDestructAction(target=None), p, base_state
        ).ok

    def test_normal_werewolf_with_target_blocked(self, base_state):
        p = base_state.get_player(2)
        assert not validate_self_destruct(
            SelfDestructAction(target=3), p, base_state
        ).ok

    def test_white_wolf_king_with_target(self, base_state):
        p = base_state.get_player(7)
        assert validate_self_destruct(
            SelfDestructAction(target=3), p, base_state
        ).ok

    def test_white_wolf_king_without_target_blocked(self, base_state):
        p = base_state.get_player(7)
        assert not validate_self_destruct(
            SelfDestructAction(target=None), p, base_state
        ).ok
