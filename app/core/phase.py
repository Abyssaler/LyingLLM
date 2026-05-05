from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    WAITING = "WAITING"
    SHERIFF_ELECTION = "SHERIFF_ELECTION"
    NIGHT_BEGIN = "NIGHT_BEGIN"
    WOLF_DISCUSS = "WOLF_DISCUSS"
    NIGHT_ACTIONS = "NIGHT_ACTIONS"
    DAWN = "DAWN"
    LAST_WORDS = "LAST_WORDS"
    WIN_CHECK = "WIN_CHECK"
    DISCUSS_ORDER = "DISCUSS_ORDER"
    DISCUSS = "DISCUSS"
    VOTE = "VOTE"
    VOTE_RESULT = "VOTE_RESULT"
    TIE_SPEECH = "TIE_SPEECH"
    TIE_VOTE = "TIE_VOTE"
    EXECUTE = "EXECUTE"
    NO_ELIMINATION = "NO_ELIMINATION"
    ON_DEATH_SKILL = "ON_DEATH_SKILL"
    GAME_END = "GAME_END"
    PAUSED = "PAUSED"
    RETRY_OR_FALLBACK = "RETRY_OR_FALLBACK"
    ABORTED = "ABORTED"


class PhaseCategory(str, Enum):
    SETUP = "setup"
    SHERIFF = "sheriff"
    NIGHT = "night"
    DAWN = "dawn"
    DAY = "day"
    TERMINAL = "terminal"
    CONTROL = "control"


PHASE_CATEGORIES: dict[Phase, PhaseCategory] = {
    Phase.WAITING: PhaseCategory.SETUP,
    Phase.SHERIFF_ELECTION: PhaseCategory.SHERIFF,
    Phase.NIGHT_BEGIN: PhaseCategory.NIGHT,
    Phase.WOLF_DISCUSS: PhaseCategory.NIGHT,
    Phase.NIGHT_ACTIONS: PhaseCategory.NIGHT,
    Phase.DAWN: PhaseCategory.DAWN,
    Phase.LAST_WORDS: PhaseCategory.DAY,
    Phase.WIN_CHECK: PhaseCategory.DAY,
    Phase.DISCUSS_ORDER: PhaseCategory.DAY,
    Phase.DISCUSS: PhaseCategory.DAY,
    Phase.VOTE: PhaseCategory.DAY,
    Phase.VOTE_RESULT: PhaseCategory.DAY,
    Phase.TIE_SPEECH: PhaseCategory.DAY,
    Phase.TIE_VOTE: PhaseCategory.DAY,
    Phase.EXECUTE: PhaseCategory.DAY,
    Phase.NO_ELIMINATION: PhaseCategory.DAY,
    Phase.ON_DEATH_SKILL: PhaseCategory.DAY,
    Phase.GAME_END: PhaseCategory.TERMINAL,
    Phase.PAUSED: PhaseCategory.CONTROL,
    Phase.RETRY_OR_FALLBACK: PhaseCategory.CONTROL,
    Phase.ABORTED: PhaseCategory.TERMINAL,
}

LLM_ACTION_PHASES: set[Phase] = {
    Phase.SHERIFF_ELECTION,
    Phase.WOLF_DISCUSS,
    Phase.NIGHT_ACTIONS,
    Phase.DISCUSS,
    Phase.VOTE,
    Phase.TIE_SPEECH,
    Phase.TIE_VOTE,
    Phase.ON_DEATH_SKILL,
}

TERMINAL_PHASES: set[Phase] = {Phase.GAME_END, Phase.ABORTED}

RUNNING_PHASES: set[Phase] = {
    Phase.WAITING,
    Phase.SHERIFF_ELECTION,
    Phase.NIGHT_BEGIN,
    Phase.WOLF_DISCUSS,
    Phase.NIGHT_ACTIONS,
    Phase.DAWN,
    Phase.LAST_WORDS,
    Phase.WIN_CHECK,
    Phase.DISCUSS_ORDER,
    Phase.DISCUSS,
    Phase.VOTE,
    Phase.VOTE_RESULT,
    Phase.TIE_SPEECH,
    Phase.TIE_VOTE,
    Phase.EXECUTE,
    Phase.NO_ELIMINATION,
    Phase.ON_DEATH_SKILL,
}

TRANSITIONS: set[tuple[Phase, Phase]] = {
    (Phase.WAITING, Phase.SHERIFF_ELECTION),
    (Phase.WAITING, Phase.NIGHT_BEGIN),
    (Phase.SHERIFF_ELECTION, Phase.NIGHT_BEGIN),
    (Phase.NIGHT_BEGIN, Phase.WOLF_DISCUSS),
    (Phase.NIGHT_BEGIN, Phase.NIGHT_ACTIONS),
    (Phase.WOLF_DISCUSS, Phase.NIGHT_ACTIONS),
    (Phase.NIGHT_ACTIONS, Phase.DAWN),
    (Phase.DAWN, Phase.LAST_WORDS),
    (Phase.DAWN, Phase.ON_DEATH_SKILL),
    (Phase.DAWN, Phase.WIN_CHECK),
    (Phase.LAST_WORDS, Phase.WIN_CHECK),
    (Phase.LAST_WORDS, Phase.ON_DEATH_SKILL),
    (Phase.WIN_CHECK, Phase.GAME_END),
    (Phase.WIN_CHECK, Phase.DISCUSS_ORDER),
    (Phase.WIN_CHECK, Phase.NIGHT_BEGIN),
    (Phase.DISCUSS_ORDER, Phase.DISCUSS),
    (Phase.DISCUSS, Phase.VOTE),
    (Phase.VOTE, Phase.VOTE_RESULT),
    (Phase.VOTE_RESULT, Phase.EXECUTE),
    (Phase.VOTE_RESULT, Phase.TIE_SPEECH),
    (Phase.VOTE_RESULT, Phase.NO_ELIMINATION),
    (Phase.EXECUTE, Phase.LAST_WORDS),
    (Phase.EXECUTE, Phase.ON_DEATH_SKILL),
    (Phase.EXECUTE, Phase.WIN_CHECK),
    (Phase.ON_DEATH_SKILL, Phase.WIN_CHECK),
    (Phase.TIE_SPEECH, Phase.TIE_VOTE),
    (Phase.TIE_VOTE, Phase.VOTE_RESULT),
    (Phase.NO_ELIMINATION, Phase.WIN_CHECK),
    (Phase.GAME_END, Phase.WAITING),
}


def get_phase_category(phase: Phase) -> PhaseCategory:
    return PHASE_CATEGORIES.get(phase, PhaseCategory.CONTROL)


def is_terminal(phase: Phase) -> bool:
    return phase in TERMINAL_PHASES


def is_llm_action(phase: Phase) -> bool:
    return phase in LLM_ACTION_PHASES


def is_running(phase: Phase) -> bool:
    return phase in RUNNING_PHASES