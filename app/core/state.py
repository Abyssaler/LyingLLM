from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.phase import (
    Phase,
    TRANSITIONS,
    LLM_ACTION_PHASES,
    RUNNING_PHASES,
    TERMINAL_PHASES,
)


class InvalidTransitionError(Exception):
    def __init__(self, from_phase: Phase, to_phase: Phase, reason: str = "") -> None:
        self.from_phase = from_phase
        self.to_phase = to_phase
        msg = f"Invalid transition: {from_phase.value} -> {to_phase.value}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class PhaseMismatchError(Exception):
    def __init__(self, expected: Phase, actual: Phase, method: str = "") -> None:
        self.expected = expected
        self.actual = actual
        msg = f"Expected phase {expected.value}, got {actual.value}"
        if method:
            msg += f" in {method}"
        super().__init__(msg)


@dataclass
class PhaseTransition:
    from_phase: Phase
    to_phase: Phase
    round: int
    reason: str = ""


class GameStateMachine:
    def __init__(self) -> None:
        self.current_phase: Phase = Phase.WAITING
        self.round: int = 0
        self._paused_from: Optional[Phase] = None
        self._retry_from: Optional[Phase] = None
        self._history: list[PhaseTransition] = []
        self._transition_callbacks: list = []

    def on_transition(self, callback) -> None:
        self._transition_callbacks.append(callback)

    def _do_transition(self, to: Phase, reason: str = "") -> None:
        from_phase = self.current_phase
        self.current_phase = to
        record = PhaseTransition(
            from_phase=from_phase, to_phase=to, round=self.round, reason=reason
        )
        self._history.append(record)
        for cb in self._transition_callbacks:
            cb(record)

    def _validate_transition(self, to: Phase) -> None:
        if to == Phase.ABORTED:
            return
        if to == Phase.PAUSED and self.current_phase in RUNNING_PHASES:
            return
        if to == Phase.RETRY_OR_FALLBACK and self.current_phase in LLM_ACTION_PHASES:
            return
        if self.current_phase == Phase.PAUSED and to == self._paused_from:
            return
        if self.current_phase == Phase.RETRY_OR_FALLBACK and to == self._retry_from:
            return
        if (self.current_phase, to) not in TRANSITIONS:
            raise InvalidTransitionError(self.current_phase, to)

    def _require_phase(self, expected: Phase, method: str = "") -> None:
        if self.current_phase != expected:
            raise PhaseMismatchError(expected, self.current_phase, method)

    # ── Setup Phase ──────────────────────────────────────────────

    def start_game(self, enable_sheriff: bool) -> Phase:
        if enable_sheriff:
            self._validate_transition(Phase.SHERIFF_ELECTION)
            self._do_transition(Phase.SHERIFF_ELECTION, reason="start_with_sheriff")
        else:
            self._validate_transition(Phase.NIGHT_BEGIN)
            self.round = 1
            self._do_transition(Phase.NIGHT_BEGIN, reason="start_no_sheriff")
        return self.current_phase

    def finish_sheriff_election(self) -> Phase:
        self._require_phase(Phase.SHERIFF_ELECTION, "finish_sheriff_election")
        self.round = 1
        self._validate_transition(Phase.NIGHT_BEGIN)
        self._do_transition(Phase.NIGHT_BEGIN, reason="sheriff_elected")
        return self.current_phase

    # ── Night Phase ──────────────────────────────────────────────

    def enter_wolf_discuss(self) -> Phase:
        self._require_phase(Phase.NIGHT_BEGIN, "enter_wolf_discuss")
        self._validate_transition(Phase.WOLF_DISCUSS)
        self._do_transition(Phase.WOLF_DISCUSS, reason="wolf_discuss_start")
        return self.current_phase

    def skip_wolf_discuss(self) -> Phase:
        if self.current_phase == Phase.NIGHT_BEGIN:
            self._validate_transition(Phase.NIGHT_ACTIONS)
            self._do_transition(Phase.NIGHT_ACTIONS, reason="skip_wolf_discuss_no_wolves")
            return self.current_phase
        self._require_phase(Phase.WOLF_DISCUSS, "skip_wolf_discuss")
        self._validate_transition(Phase.NIGHT_ACTIONS)
        self._do_transition(Phase.NIGHT_ACTIONS, reason="skip_wolf_discuss")
        return self.current_phase

    def finish_wolf_discuss(self) -> Phase:
        self._require_phase(Phase.WOLF_DISCUSS, "finish_wolf_discuss")
        self._validate_transition(Phase.NIGHT_ACTIONS)
        self._do_transition(Phase.NIGHT_ACTIONS, reason="wolf_discuss_done")
        return self.current_phase

    def finish_night_actions(self) -> Phase:
        self._require_phase(Phase.NIGHT_ACTIONS, "finish_night_actions")
        self._validate_transition(Phase.DAWN)
        self._do_transition(Phase.DAWN, reason="night_actions_done")
        return self.current_phase

    # ── Dawn Resolution ───────────────────────────────────────────

    def resolve_dawn(
        self,
        has_deaths: bool,
        has_last_words: bool = False,
        has_death_skill: bool = False,
    ) -> Phase:
        self._require_phase(Phase.DAWN, "resolve_dawn")
        if has_death_skill and has_last_words:
            self._validate_transition(Phase.LAST_WORDS)
            self._do_transition(Phase.LAST_WORDS, reason="dawn_death_skill_with_last_words")
        elif has_death_skill:
            self._validate_transition(Phase.ON_DEATH_SKILL)
            self._do_transition(Phase.ON_DEATH_SKILL, reason="dawn_death_skill")
        elif has_deaths and has_last_words:
            self._validate_transition(Phase.LAST_WORDS)
            self._do_transition(Phase.LAST_WORDS, reason="dawn_deaths_with_last_words")
        else:
            self._validate_transition(Phase.WIN_CHECK)
            self._do_transition(Phase.WIN_CHECK, reason="dawn_to_win_check")
        return self.current_phase

    # ── Last Words ────────────────────────────────────────────────

    def finish_last_words(self, has_death_skill: bool = False) -> Phase:
        self._require_phase(Phase.LAST_WORDS, "finish_last_words")
        if has_death_skill:
            self._validate_transition(Phase.ON_DEATH_SKILL)
            self._do_transition(Phase.ON_DEATH_SKILL, reason="last_words_then_death_skill")
        else:
            self._validate_transition(Phase.WIN_CHECK)
            self._do_transition(Phase.WIN_CHECK, reason="last_words_to_win_check")
        return self.current_phase

    # ── Win Check ─────────────────────────────────────────────────

    def check_win(self, has_winner: bool, after_night: bool) -> Phase:
        self._require_phase(Phase.WIN_CHECK, "check_win")
        if has_winner:
            self._validate_transition(Phase.GAME_END)
            self._do_transition(Phase.GAME_END, reason="winner_found")
            return self.current_phase
        if after_night:
            self._validate_transition(Phase.DISCUSS_ORDER)
            self._do_transition(Phase.DISCUSS_ORDER, reason="no_winner_start_day")
            return self.current_phase
        self.round += 1
        self._validate_transition(Phase.NIGHT_BEGIN)
        self._do_transition(Phase.NIGHT_BEGIN, reason="no_winner_start_night")
        return self.current_phase

    # ── Day Phase ─────────────────────────────────────────────────

    def start_discuss(self) -> Phase:
        self._require_phase(Phase.DISCUSS_ORDER, "start_discuss")
        self._validate_transition(Phase.DISCUSS)
        self._do_transition(Phase.DISCUSS, reason="discuss_start")
        return self.current_phase

    def finish_discuss(self) -> Phase:
        self._require_phase(Phase.DISCUSS, "finish_discuss")
        self._validate_transition(Phase.VOTE)
        self._do_transition(Phase.VOTE, reason="discuss_done")
        return self.current_phase

    def finish_vote(self) -> Phase:
        self._require_phase(Phase.VOTE, "finish_vote")
        self._validate_transition(Phase.VOTE_RESULT)
        self._do_transition(Phase.VOTE_RESULT, reason="vote_done")
        return self.current_phase

    def resolve_vote_result(self, result: str) -> Phase:
        self._require_phase(Phase.VOTE_RESULT, "resolve_vote_result")
        if result == "majority":
            self._validate_transition(Phase.EXECUTE)
            self._do_transition(Phase.EXECUTE, reason="vote_majority")
        elif result == "tie":
            self._validate_transition(Phase.TIE_SPEECH)
            self._do_transition(Phase.TIE_SPEECH, reason="vote_tie")
        elif result == "all_abstain":
            self._validate_transition(Phase.NO_ELIMINATION)
            self._do_transition(Phase.NO_ELIMINATION, reason="all_abstain")
        else:
            raise InvalidTransitionError(
                self.current_phase, self.current_phase, f"Unknown vote result: {result}"
            )
        return self.current_phase

    # ── Tie Handling ──────────────────────────────────────────────

    def finish_tie_speech(self) -> Phase:
        self._require_phase(Phase.TIE_SPEECH, "finish_tie_speech")
        self._validate_transition(Phase.TIE_VOTE)
        self._do_transition(Phase.TIE_VOTE, reason="tie_speech_done")
        return self.current_phase

    def finish_tie_vote(self) -> Phase:
        self._require_phase(Phase.TIE_VOTE, "finish_tie_vote")
        self._validate_transition(Phase.VOTE_RESULT)
        self._do_transition(Phase.VOTE_RESULT, reason="tie_vote_done")
        return self.current_phase

    # ── Execution ─────────────────────────────────────────────────

    def finish_execute(
        self,
        has_last_words: bool = True,
        has_death_skill: bool = False,
    ) -> Phase:
        self._require_phase(Phase.EXECUTE, "finish_execute")
        if has_last_words:
            self._validate_transition(Phase.LAST_WORDS)
            self._do_transition(Phase.LAST_WORDS, reason="execute_then_last_words")
        elif has_death_skill:
            self._validate_transition(Phase.ON_DEATH_SKILL)
            self._do_transition(Phase.ON_DEATH_SKILL, reason="execute_then_death_skill")
        else:
            self._validate_transition(Phase.WIN_CHECK)
            self._do_transition(Phase.WIN_CHECK, reason="execute_to_win_check")
        return self.current_phase

    # ── No Elimination ────────────────────────────────────────────

    def finish_no_elimination(self) -> Phase:
        self._require_phase(Phase.NO_ELIMINATION, "finish_no_elimination")
        self._validate_transition(Phase.WIN_CHECK)
        self._do_transition(Phase.WIN_CHECK, reason="no_elimination_to_win_check")
        return self.current_phase

    # ── On-Death Skill ────────────────────────────────────────────

    def finish_on_death_skill(self) -> Phase:
        self._require_phase(Phase.ON_DEATH_SKILL, "finish_on_death_skill")
        self._validate_transition(Phase.WIN_CHECK)
        self._do_transition(Phase.WIN_CHECK, reason="death_skill_to_win_check")
        return self.current_phase

    # ── Control Flow ──────────────────────────────────────────────

    def pause(self) -> Phase:
        if self.current_phase not in RUNNING_PHASES:
            raise InvalidTransitionError(
                self.current_phase, Phase.PAUSED, "Can only pause from running phase"
            )
        self._paused_from = self.current_phase
        self._do_transition(Phase.PAUSED, reason="pause")
        return self.current_phase

    def resume(self) -> Phase:
        self._require_phase(Phase.PAUSED, "resume")
        if self._paused_from is None:
            raise InvalidTransitionError(Phase.PAUSED, Phase.WAITING, "No paused phase to resume to")
        target = self._paused_from
        self._paused_from = None
        self._do_transition(target, reason="resume")
        return self.current_phase

    def enter_retry(self, reason: str = "") -> Phase:
        if self.current_phase not in LLM_ACTION_PHASES:
            raise InvalidTransitionError(
                self.current_phase, Phase.RETRY_OR_FALLBACK,
                "Can only retry from LLM action phase"
            )
        self._retry_from = self.current_phase
        self._do_transition(Phase.RETRY_OR_FALLBACK, reason=reason or "llm_retry")
        return self.current_phase

    def finish_retry(self) -> Phase:
        self._require_phase(Phase.RETRY_OR_FALLBACK, "finish_retry")
        if self._retry_from is None:
            raise InvalidTransitionError(
                Phase.RETRY_OR_FALLBACK, Phase.WAITING, "No retry phase to return to"
            )
        target = self._retry_from
        self._retry_from = None
        self._do_transition(target, reason="retry_success")
        return self.current_phase

    def abort(self, reason: str = "") -> Phase:
        self._do_transition(Phase.ABORTED, reason=reason or "abort")
        return self.current_phase

    def end_game(self) -> Phase:
        if self.current_phase not in (Phase.WIN_CHECK, Phase.ABORTED):
            raise InvalidTransitionError(self.current_phase, Phase.GAME_END, "Can only end from WIN_CHECK")
        self._do_transition(Phase.GAME_END, reason="game_end")
        return self.current_phase

    def reset(self) -> None:
        self.current_phase = Phase.WAITING
        self.round = 0
        self._paused_from = None
        self._retry_from = None
        self._history.clear()

    @property
    def history(self) -> list[PhaseTransition]:
        return list(self._history)

    @property
    def paused_from(self) -> Optional[Phase]:
        return self._paused_from

    @property
    def retry_from(self) -> Optional[Phase]:
        return self._retry_from