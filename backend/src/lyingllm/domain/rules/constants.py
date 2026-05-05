"""Rule constants derived from ``rule.md`` §10.

These are the single source of truth for all rule numbers used by the engine.
"""

from __future__ import annotations

PLAYER_COUNT = 12

# role_id -> count for a standard 12-player game
ROLE_COUNTS: dict[str, int] = {
    "seer": 1,
    "witch": 1,
    "hunter": 1,
    "guard": 1,
    "villager": 4,
    "werewolf": 3,
    "white_wolf_king": 1,
}

WOLF_ROLES = {"werewolf", "white_wolf_king"}
GOD_ROLES = {"seer", "witch", "hunter", "guard"}
VILLAGER_ROLES = {"villager"}

NIGHT_ORDER = ["guard", "wolves", "witch", "seer"]

# Sheriff
SHERIFF_ENABLED = True
SHERIFF_VOTE_WEIGHT = 1.5
SHERIFF_REVOTE_IF_TIE = True
SHERIFF_NO_SHERIFF_IF_REVOTE_TIE = True
SHERIFF_CAN_TRANSFER_ON_DEATH = True

# Witch
WITCH_CAN_SELF_SAVE = True
WITCH_CANNOT_USE_BOTH_POTIONS_SAME_NIGHT = True
WITCH_LOSES_KILL_INFO_AFTER_SAVE_USED = True
WITCH_POISON_BLOCKS_HUNTER_SHOT = True

# Guard
GUARD_CAN_SELF_GUARD = True
GUARD_CAN_SKIP_GUARD = True
GUARD_CANNOT_GUARD_SAME_PLAYER_CONSECUTIVELY = True
GUARD_AND_SAVE_SAME_TARGET_DIES = True

# Hunter
HUNTER_CAN_SHOOT_WHEN_KILLED_BY_WOLVES = True
HUNTER_CAN_SHOOT_WHEN_EXILED = True
HUNTER_CAN_SHOOT_WHEN_TAKEN_BY_WHITE_WOLF_KING = True
HUNTER_CAN_SHOOT_WHEN_POISONED = False

# Vote
VOTE_EXILE_RULE = "highest_votes"
VOTE_ALLOW_ABSTAIN = True
VOTE_ABSTAIN_COUNTS_AS_CANDIDATE_VOTE = False
VOTE_REVOTE_IF_TIE = True
VOTE_NO_ELIMINATION_IF_REVOTE_TIE = True

# Last words
LAST_WORDS_FIRST_NIGHT_DEATHS = True
LAST_WORDS_NIGHT_DEATHS_AFTER_FIRST_NIGHT = False
LAST_WORDS_DAY_EXILE_DEATHS = True
LAST_WORDS_DAY_SKILL_DEATHS = True
LAST_WORDS_DEATH_SKILL_BEFORE_LAST_WORDS = True

# Self destruct
NORMAL_WEREWOLF_CAN_SELF_DESTRUCT = True
NORMAL_WEREWOLF_TAKES_PLAYER = False
WHITE_WOLF_KING_CAN_SELF_DESTRUCT = True
WHITE_WOLF_KING_TAKES_PLAYER = True
SELF_DESTRUCT_ENDS_CURRENT_DAY = True

# Night tie-breaker
NIGHT_TIE_BREAKER_WOLVES_WIN = True
