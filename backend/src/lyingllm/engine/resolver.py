"""Night resolution and win-condition checking.

This is the only module that decides *who dies at night* and *who wins*.
"""

from __future__ import annotations

from lyingllm.domain.models.player import Player, RoleId, Faction
from lyingllm.domain.models.game import (
    GameState,
    NightActionSet,
    DeathRecord,
    DeathCause,
)
from lyingllm.domain.rules import constants as C


def resolve_night(
    state: GameState,
    night_actions: NightActionSet,
) -> list[DeathRecord]:
    """Resolve a single night's actions into a list of death records.

    The returned list is already sorted by player_id ascending (same-batch
    ordering).  Deaths caused by death-skills are handled later by the
    engine's death-queue processor, not here.
    """
    deaths: dict[int, DeathRecord] = {}

    wolf_target = night_actions.wolf_kill_target
    guard_target = night_actions.guard_target
    save_used = night_actions.witch_save_used
    poison_target = night_actions.witch_poison_target

    # --- wolf kill ----------------------------------------------------------
    if wolf_target is not None:
        guarded = guard_target == wolf_target
        saved = save_used

        if guarded and saved:
            # 同守同救 → dies
            _add_death(
                deaths,
                wolf_target,
                timing="night",
                round_no=state.round_no,
                cause=DeathCause.GUARD_AND_SAVE,
            )
        elif guarded and not saved:
            # guarded, no save → blocked
            pass
        elif not guarded and saved:
            # saved, not guarded → blocked
            pass
        else:
            # not guarded, not saved → dies
            _add_death(
                deaths,
                wolf_target,
                timing="night",
                round_no=state.round_no,
                cause=DeathCause.WOLF_KILL,
            )

    # --- witch poison -------------------------------------------------------
    if poison_target is not None:
        _add_death(
            deaths,
            poison_target,
            timing="night",
            round_no=state.round_no,
            cause=DeathCause.WITCH_POISON,
        )

    # --- build sorted list --------------------------------------------------
    result = [deaths[pid] for pid in sorted(deaths)]

    # --- set can_trigger_death_skill for poisoned hunters -------------------
    for dr in result:
        player = state.get_player(dr.player_id)
        if player is None:
            continue
        if player.role == RoleId.HUNTER:
            if DeathCause.WITCH_POISON in dr.causes:
                dr.can_trigger_death_skill = False
            else:
                dr.can_trigger_death_skill = True

    # --- last-words eligibility (night deaths) ------------------------------
    for dr in result:
        dr.has_last_words = C.LAST_WORDS_FIRST_NIGHT_DEATHS if state.is_first_night else C.LAST_WORDS_NIGHT_DEATHS_AFTER_FIRST_NIGHT

    return result


def _add_death(
    deaths: dict[int, DeathRecord],
    player_id: int,
    timing: str,
    round_no: int,
    cause: DeathCause,
) -> None:
    if player_id in deaths:
        deaths[player_id].causes.append(cause)
    else:
        deaths[player_id] = DeathRecord(
            player_id=player_id,
            timing=timing,
            round_no=round_no,
            causes=[cause],
        )


def check_win(state: GameState) -> Faction | None:
    """Return the winning faction, or ``None`` if the game continues.

    Night tie-breaker: if wolves wipe out gods AND all wolves die in the
    same night resolution, wolves win (wolf-kill-first principle).
    """
    alive_gods = state.alive_gods
    alive_villagers = state.alive_villagers
    alive_wolves = state.alive_wolves

    wolves_win = alive_gods == 0 or alive_villagers == 0
    village_win = alive_wolves == 0

    if wolves_win and village_win:
        # tie-breaker: wolves win
        return Faction.WOLF
    if wolves_win:
        return Faction.WOLF
    if village_win:
        return Faction.VILLAGE
    return None
