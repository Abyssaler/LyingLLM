"""Unit tests for domain models and rule constants."""

import random

import pytest

from lyingllm.domain.models.player import Player, RoleId
from lyingllm.domain.models.game import (
    GameState,
    NightActionSet,
    VoteState,
    SheriffElectionState,
    DeathRecord,
    DeathCause,
    Phase,
    GameSetupConfig,
    PlayerSetupConfig,
)
from lyingllm.domain.rules.constants import ROLE_COUNTS, WOLF_ROLES, GOD_ROLES
from lyingllm.domain.rules.roles import assign_roles


class TestPlayer:
    def test_alive_wolves_includes_white_wolf_king(self):
        """white_wolf_king counts toward alive_wolves."""
        p1 = Player(id=1, role=RoleId.WEREWOLF)
        p2 = Player(id=2, role=RoleId.WHITE_WOLF_KING)
        p3 = Player(id=3, role=RoleId.VILLAGER)
        state = GameState(game_id="test", players=[p1, p2, p3])
        assert state.alive_wolves == 2

    def test_alive_gods(self):
        p1 = Player(id=1, role=RoleId.SEER)
        p2 = Player(id=2, role=RoleId.WITCH)
        p3 = Player(id=3, role=RoleId.VILLAGER)
        state = GameState(game_id="test", players=[p1, p2, p3])
        assert state.alive_gods == 2

    def test_alive_villagers(self):
        p1 = Player(id=1, role=RoleId.VILLAGER)
        p2 = Player(id=2, role=RoleId.WEREWOLF)
        state = GameState(game_id="test", players=[p1, p2])
        assert state.alive_villagers == 1


class TestRoleAssignment:
    def test_assign_roles_has_correct_counts(self):
        roles = assign_roles(rng=random.Random(42))
        assert len(roles) == 12
        counts = {}
        for r in roles:
            counts[r.value] = counts.get(r.value, 0) + 1
        assert counts == ROLE_COUNTS

    def test_assign_roles_is_random(self):
        r1 = assign_roles(rng=random.Random(1))
        r2 = assign_roles(rng=random.Random(2))
        assert r1 != r2


class TestGameSetupConfig:
    def test_must_be_12_players(self):
        with pytest.raises(ValueError):
            GameSetupConfig(players=[])

    def test_duplicate_player_ids_rejected(self):
        players = [PlayerSetupConfig(player_id=1)] * 12
        with pytest.raises(ValueError):
            GameSetupConfig(players=players)

    def test_valid_config(self):
        players = [PlayerSetupConfig(player_id=i) for i in range(1, 13)]
        cfg = GameSetupConfig(players=players)
        assert len(cfg.players) == 12


class TestGameStateProperties:
    def test_is_first_night(self):
        state = GameState(game_id="t", round_no=1)
        assert state.is_first_night is True
        state.round_no = 2
        assert state.is_first_night is False

    def test_get_player(self):
        p = Player(id=5, role=RoleId.SEER)
        state = GameState(game_id="t", players=[p])
        assert state.get_player(5) == p
        assert state.get_player(99) is None


class TestDeathRecord:
    def test_multi_cause_death(self):
        dr = DeathRecord(
            player_id=1,
            timing="night",
            round_no=1,
            causes=[DeathCause.WOLF_KILL, DeathCause.GUARD_AND_SAVE],
        )
        assert len(dr.causes) == 2


class TestNightActionSet:
    def test_wolf_kill_target_is_optional_at_init(self):
        na = NightActionSet(round_no=1)
        assert na.wolf_kill_target is None
