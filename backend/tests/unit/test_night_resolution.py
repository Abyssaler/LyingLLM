"""Tests for night resolution, death queue, and win conditions."""

import pytest

from lyingllm.domain.models.player import Player, RoleId, Faction
from lyingllm.domain.models.game import GameState, NightActionSet, DeathRecord, DeathCause
from lyingllm.domain.rules.constants import ROLE_COUNTS
from lyingllm.engine.resolver import resolve_night, check_win


def make_12_player_state(**kwargs) -> GameState:
    """Return a full 12-player state with standard roles."""
    roles = []
    for r, c in ROLE_COUNTS.items():
        roles.extend([RoleId(r)] * c)
    # deterministic order for testing
    players = [Player(id=i + 1, role=roles[i]) for i in range(12)]
    return GameState(game_id="test", players=players, **kwargs)


class TestAliveWolvesIncludesWhiteWolfKing:
    def test_alive_wolves_includes_white_wolf_king(self):
        state = make_12_player_state()
        # By default all alive
        assert state.alive_wolves == 4  # 3 werewolf + 1 white_wolf_king


class TestGuardBlocksWolfKill:
    def test_guard_blocks_wolf_kill(self):
        state = make_12_player_state(round_no=1)
        na = NightActionSet(
            round_no=1,
            guard_target=3,
            wolf_kill_target=3,
            witch_save_used=False,
        )
        deaths = resolve_night(state, na)
        assert len(deaths) == 0


class TestGuardAndWitchSaveSameTargetDies:
    def test_guard_and_witch_save_same_target_dies(self):
        state = make_12_player_state(round_no=1)
        na = NightActionSet(
            round_no=1,
            guard_target=3,
            wolf_kill_target=3,
            witch_save_used=True,
        )
        deaths = resolve_night(state, na)
        assert len(deaths) == 1
        assert deaths[0].player_id == 3
        assert DeathCause.GUARD_AND_SAVE in deaths[0].causes


class TestWitchPoisonBlocksHunterShot:
    def test_witch_poison_blocks_hunter_shot(self):
        state = make_12_player_state(round_no=1)
        # Find hunter player id
        hunter = next(p for p in state.players if p.role == RoleId.HUNTER)
        na = NightActionSet(
            round_no=1,
            witch_poison_target=hunter.id,
        )
        deaths = resolve_night(state, na)
        hunter_dr = next(d for d in deaths if d.player_id == hunter.id)
        assert hunter_dr.can_trigger_death_skill is False


class TestFirstNightDeathHasLastWords:
    def test_first_night_death_has_last_words(self):
        state = make_12_player_state(round_no=1)
        na = NightActionSet(round_no=1, wolf_kill_target=3)
        deaths = resolve_night(state, na)
        assert all(d.has_last_words for d in deaths)


class TestSecondNightDeathHasNoLastWords:
    def test_second_night_death_has_no_last_words(self):
        state = make_12_player_state(round_no=2)
        na = NightActionSet(round_no=2, wolf_kill_target=3)
        deaths = resolve_night(state, na)
        assert all(not d.has_last_words for d in deaths)


class TestNightTieBreakerWolvesWin:
    def test_night_tie_breaker_wolves_win(self):
        """If wolves kill last god and last wolf dies same night, wolves win."""
        state = make_12_player_state(round_no=1)
        # Kill all but one god and all wolves via poison (not realistic but tests rule)
        # Actually let's just set up counts directly by killing players
        for p in state.players:
            if p.role_group.value == "god" and state.alive_gods > 1:
                p.alive = False
            if p.role in (RoleId.WEREWOLF, RoleId.WHITE_WOLF_KING) and state.alive_wolves > 1:
                p.alive = False
        # Now we have 1 god alive, 1 wolf alive, some villagers
        # Simulate a night where both die
        na = NightActionSet(
            round_no=1,
            wolf_kill_target=next(p.id for p in state.players if p.role_group.value == "god" and p.alive),
            witch_poison_target=next(p.id for p in state.players if p.role in (RoleId.WEREWOLF, RoleId.WHITE_WOLF_KING) and p.alive),
        )
        deaths = resolve_night(state, na)
        # Apply deaths
        for d in deaths:
            p = state.get_player(d.player_id)
            if p:
                p.alive = False
        winner = check_win(state)
        assert winner == Faction.WOLF


class TestWitchSaveBlocksKill:
    def test_witch_save_blocks_kill(self):
        state = make_12_player_state(round_no=1)
        na = NightActionSet(
            round_no=1,
            wolf_kill_target=3,
            witch_save_used=True,
        )
        deaths = resolve_night(state, na)
        assert len(deaths) == 0


class TestPoisonKills:
    def test_poison_kills(self):
        state = make_12_player_state(round_no=1)
        na = NightActionSet(round_no=1, witch_poison_target=3)
        deaths = resolve_night(state, na)
        assert len(deaths) == 1
        assert DeathCause.WITCH_POISON in deaths[0].causes


class TestMultiCauseDeath:
    def test_wolf_kill_and_poison_same_target(self):
        state = make_12_player_state(round_no=1)
        na = NightActionSet(
            round_no=1,
            wolf_kill_target=3,
            witch_poison_target=3,
        )
        deaths = resolve_night(state, na)
        assert len(deaths) == 1
        assert DeathCause.WOLF_KILL in deaths[0].causes
        assert DeathCause.WITCH_POISON in deaths[0].causes


class TestWinCondition:
    def test_wolves_win_when_all_gods_dead(self):
        state = make_12_player_state()
        for p in state.players:
            if p.role_group.value == "god":
                p.alive = False
        assert check_win(state) == Faction.WOLF

    def test_wolves_win_when_all_villagers_dead(self):
        state = make_12_player_state()
        for p in state.players:
            if p.role_group.value == "villager":
                p.alive = False
        assert check_win(state) == Faction.WOLF

    def test_village_win_when_all_wolves_dead(self):
        state = make_12_player_state()
        for p in state.players:
            if p.role in (RoleId.WEREWOLF, RoleId.WHITE_WOLF_KING):
                p.alive = False
        assert check_win(state) == Faction.VILLAGE

    def test_no_winner_mid_game(self):
        state = make_12_player_state()
        assert check_win(state) is None

    def test_night_tie_breaker(self):
        """Simultaneous gods=0 and wolves=0 → wolves win."""
        state = make_12_player_state()
        # Kill all gods and all wolves in one batch
        for p in state.players:
            if p.role_group.value == "god" or p.role in (RoleId.WEREWOLF, RoleId.WHITE_WOLF_KING):
                p.alive = False
        assert check_win(state) == Faction.WOLF
