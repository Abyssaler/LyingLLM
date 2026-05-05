"""Player model and role enumerations.

Rules are the single source of truth — see ``rule.md`` §1 and §3.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any


class RoleId(str, Enum):
    """Fixed role identifiers for a 12-player standard game."""

    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    GUARD = "guard"
    VILLAGER = "villager"
    WEREWOLF = "werewolf"
    WHITE_WOLF_KING = "white_wolf_king"


class Faction(str, Enum):
    VILLAGE = "village"
    WOLF = "wolf"


class RoleGroup(str, Enum):
    GOD = "god"
    VILLAGER = "villager"
    WOLF = "wolf"


_ROLE_FACTION: dict[RoleId, Faction] = {
    RoleId.SEER: Faction.VILLAGE,
    RoleId.WITCH: Faction.VILLAGE,
    RoleId.HUNTER: Faction.VILLAGE,
    RoleId.GUARD: Faction.VILLAGE,
    RoleId.VILLAGER: Faction.VILLAGE,
    RoleId.WEREWOLF: Faction.WOLF,
    RoleId.WHITE_WOLF_KING: Faction.WOLF,
}

_ROLE_GROUP: dict[RoleId, RoleGroup] = {
    RoleId.SEER: RoleGroup.GOD,
    RoleId.WITCH: RoleGroup.GOD,
    RoleId.HUNTER: RoleGroup.GOD,
    RoleId.GUARD: RoleGroup.GOD,
    RoleId.VILLAGER: RoleGroup.VILLAGER,
    RoleId.WEREWOLF: RoleGroup.WOLF,
    RoleId.WHITE_WOLF_KING: RoleGroup.WOLF,
}


def get_faction(role: RoleId) -> Faction:
    return _ROLE_FACTION[role]


def get_role_group(role: RoleId) -> RoleGroup:
    return _ROLE_GROUP[role]


class Player:
    """A game participant.

    Not a Pydantic model — it is created and mutated only by the engine.
    """

    def __init__(
        self,
        *,
        id: int,
        role: RoleId,
        alive: bool = True,
        is_sheriff: bool = False,
        model_config: Any | None = None,
    ) -> None:
        if not (1 <= id <= 12):
            raise ValueError("Player id must be 1..12")
        self.id = id
        self.role = role
        self.faction = get_faction(role)
        self.role_group = get_role_group(role)
        self.alive = alive
        self.is_sheriff = is_sheriff
        self.model_config = model_config

        # Engine-managed mutable state
        self.witch_save_used: bool = False
        self.witch_poison_used: bool = False
        self.last_guard_target: int | None = None  # None = no guard or skipped
        self.can_shoot: bool = True
        self.checked_players: set[int] = set()  # seer only

    def __repr__(self) -> str:
        return f"Player({self.id}, {self.role.value}, alive={self.alive})"
