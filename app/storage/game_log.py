from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.models.event import (
    DeathCause,
    DeathRecord,
    EventVisibility,
    GameEvent,
    GameLog,
    NightActionSet,
    NightResolutionResult,
    PrivateResult,
    VoteRecord,
    VoteResult,
    VoteSummary,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"


class GameLogStorage:
    def __init__(self, game_id: str, log_dir: str | Path | None = None) -> None:
        self.game_id = game_id
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        self._event_counter: int = 0
        self._day_log: list[GameEvent] = []
        self._night_log: list[GameEvent] = []
        self._observer_log: list[GameEvent] = []
        self._private_events: list[GameEvent] = []
        self._config: dict[str, Any] = {}

    def _next_event_id(self) -> int:
        self._event_counter += 1
        return self._event_counter

    def _current_timestamp(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def add_event(
        self,
        event_type: str,
        phase: str,
        round_num: int,
        visibility: list[str] | None = None,
        player_id: int | None = None,
        data: dict[str, Any] | None = None,
        raw_model_output: dict[str, Any] | None = None,
        validated_action: dict[str, Any] | None = None,
        causation_id: int | None = None,
    ) -> GameEvent:
        if visibility is None:
            visibility = ["public"]
        event = GameEvent(
            event_id=self._next_event_id(),
            game_id=self.game_id,
            round=round_num,
            phase=phase,
            event_type=event_type,
            player_id=player_id,
            visibility=visibility,
            causation_id=causation_id,
            data=data or {},
            raw_model_output=raw_model_output,
            validated_action=validated_action,
            timestamp=datetime.utcnow(),
        )
        self._route_event(event)
        return event

    def _route_event(self, event: GameEvent) -> None:
        vis = set(event.visibility)
        if "observer" in vis:
            self._observer_log.append(event)
        if "public" in vis or vis & {"public"}:
            self._day_log.append(event)
            if "observer" not in vis:
                pass

        is_night_phase = any(
            keyword in event.phase
            for keyword in ("night", "wolf_discuss", "dawn")
        )
        if is_night_phase and event.event_type not in ("phase_change",):
            if event not in self._night_log:
                self._night_log.append(event)

        if "private" in vis or any(
            v.startswith("player:") for v in vis
        ):
            self._private_events.append(event)

        if "faction" in vis:
            self._private_events.append(event)

        if event not in self._day_log and event.event_type not in ("phase_change",):
            self._day_log.append(event)

    def add_day_event(
        self,
        event_type: str,
        phase: str,
        round_num: int,
        player_id: int | None = None,
        data: dict[str, Any] | None = None,
        visibility: list[str] | None = None,
    ) -> GameEvent:
        if visibility is None:
            visibility = ["public"]
        return self.add_event(
            event_type=event_type,
            phase=phase,
            round_num=round_num,
            visibility=visibility,
            player_id=player_id,
            data=data,
        )

    def add_night_event(
        self,
        event_type: str,
        phase: str,
        round_num: int,
        player_id: int | None = None,
        data: dict[str, Any] | None = None,
        visibility: list[str] | None = None,
    ) -> GameEvent:
        if visibility is None:
            visibility = ["observer"]
        return self.add_event(
            event_type=event_type,
            phase=phase,
            round_num=round_num,
            visibility=visibility,
            player_id=player_id,
            data=data,
        )

    def add_thinking_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        thinking: str,
        raw_output: dict[str, Any] | None = None,
    ) -> GameEvent:
        return self.add_event(
            event_type="thinking",
            phase=phase,
            round_num=round_num,
            visibility=["observer", f"player:{player_id}"],
            player_id=player_id,
            data={"thinking": thinking},
            raw_model_output=raw_output,
        )

    def add_speech_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        content: str,
        validated_action: dict[str, Any] | None = None,
        raw_output: dict[str, Any] | None = None,
    ) -> GameEvent:
        return self.add_event(
            event_type="speech",
            phase=phase,
            round_num=round_num,
            visibility=["public"],
            player_id=player_id,
            data={"content": content},
            validated_action=validated_action,
            raw_model_output=raw_output,
        )

    def add_vote_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        target_id: int | None,
        is_abstain: bool = False,
    ) -> GameEvent:
        return self.add_event(
            event_type="vote",
            phase=phase,
            round_num=round_num,
            visibility=["public"],
            player_id=player_id,
            data={"target": target_id, "is_abstain": is_abstain},
        )

    def add_vote_result_event(
        self,
        phase: str,
        round_num: int,
        vote_summary: VoteSummary,
    ) -> GameEvent:
        return self.add_event(
            event_type="vote_result",
            phase=phase,
            round_num=round_num,
            visibility=["public"],
            data={
                "result": vote_summary.result.value,
                "eliminated_id": vote_summary.eliminated_id,
                "tied_ids": vote_summary.tied_ids,
                "votes": [v.model_dump() for v in vote_summary.votes],
            },
        )

    def add_death_event(
        self,
        phase: str,
        round_num: int,
        deaths: list[DeathRecord],
        announcement: str,
    ) -> GameEvent:
        return self.add_event(
            event_type="deaths",
            phase=phase,
            round_num=round_num,
            visibility=["public"],
            data={
                "announcement": announcement,
                "dead_player_ids": [d.player_id for d in deaths],
            },
        )

    def add_night_action_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        role: str,
        action_type: str,
        target_id: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> GameEvent:
        action_data: dict[str, Any] = {
            "role": role,
            "action_type": action_type,
        }
        if target_id is not None:
            action_data["target"] = target_id
        if data:
            action_data.update(data)
        return self.add_event(
            event_type="night_action",
            phase=phase,
            round_num=round_num,
            visibility=["observer"],
            player_id=player_id,
            data=action_data,
        )

    def add_private_result_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        result_type: str,
        result_data: dict[str, Any],
    ) -> GameEvent:
        return self.add_event(
            event_type="private_result",
            phase=phase,
            round_num=round_num,
            visibility=[f"player:{player_id}"],
            player_id=player_id,
            data={"result_type": result_type, **result_data},
        )

    def add_night_resolution(
        self,
        round_num: int,
        resolution: NightResolutionResult,
    ) -> list[GameEvent]:
        events: list[GameEvent] = []
        if resolution.public_announcement:
            events.append(self.add_death_event(
                phase=f"night_{round_num}",
                round_num=round_num,
                deaths=resolution.deaths,
                announcement=resolution.public_announcement,
            ))
        for dr in resolution.death_causes:
            events.append(self.add_event(
                event_type="death_cause",
                phase=f"night_{round_num}",
                round_num=round_num,
                visibility=["observer"],
                data={"player_id": dr.player_id, "causes": [c.value for c in dr.causes]},
            ))
        for pr in resolution.private_results:
            events.append(self.add_private_result_event(
                phase=f"night_{round_num}",
                round_num=round_num,
                player_id=pr.player_id,
                result_type=pr.result_type,
                result_data=pr.data,
            ))
        return events

    def add_last_words_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        content: str,
    ) -> GameEvent:
        return self.add_event(
            event_type="last_words",
            phase=phase,
            round_num=round_num,
            visibility=["public"],
            player_id=player_id,
            data={"content": content},
        )

    def add_on_death_skill_event(
        self,
        phase: str,
        round_num: int,
        player_id: int,
        skill_type: str,
        target_id: int | None = None,
        sheriff_transfer: int | None = None,
    ) -> GameEvent:
        data: dict[str, Any] = {"skill_type": skill_type}
        if target_id is not None:
            data["target"] = target_id
        if sheriff_transfer is not None:
            data["sheriff_transfer"] = sheriff_transfer
        return self.add_event(
            event_type="on_death_skill",
            phase=phase,
            round_num=round_num,
            visibility=["public", "observer"],
            player_id=player_id,
            data=data,
        )

    def add_phase_change_event(
        self,
        from_phase: str,
        to_phase: str,
        round_num: int,
    ) -> GameEvent:
        return self.add_event(
            event_type="phase_change",
            phase=to_phase,
            round_num=round_num,
            visibility=["public"],
            data={"from_phase": from_phase, "to_phase": to_phase},
        )

    def set_config(self, config: dict[str, Any]) -> None:
        self._config = config

    def set_result(self, winner: str, rounds: int) -> None:
        self._result = {"winner": winner, "rounds": rounds}

    def set_mvp(self, player_id: int, role: str, model: str, reason: str) -> None:
        self._mvp = {
            "player_id": player_id,
            "role": role,
            "model": model,
            "reason": reason,
        }

    def build_log(self) -> GameLog:
        return GameLog(
            schema_version="1.0",
            game_id=self.game_id,
            config=self._config,
            day_log=list(self._day_log),
            night_log=list(self._night_log),
            observer_log=list(self._observer_log),
            private_events=list(self._private_events),
            result=getattr(self, "_result", None),
            mvp=getattr(self, "_mvp", None),
        )

    def save_to_file(self, filepath: str | Path | None = None) -> Path:
        if filepath is None:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            filepath = self.log_dir / f"{self.game_id}.json"
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        log = self.build_log()
        data = log.model_dump(mode="json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return filepath

    @classmethod
    def load_from_file(cls, filepath: str | Path) -> GameLogStorage:
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        game_id = data.get("game_id", uuid4().hex)
        storage = cls(game_id=game_id)
        log = GameLog(**data)
        storage._config = log.config or {}
        storage._day_log = list(log.day_log)
        storage._night_log = list(log.night_log)
        storage._observer_log = list(log.observer_log)
        storage._private_events = list(log.private_events)
        if log.result:
            storage._result = log.result
        if log.mvp:
            storage._mvp = log.mvp
        storage._event_counter = max(
            (e.event_id for e in log.day_log + log.night_log + log.observer_log + log.private_events),
            default=0,
        )
        return storage

    def get_events_after(self, after_event_id: int, visibility: str | None = None) -> list[GameEvent]:
        all_events: list[GameEvent] = []
        all_events.extend(self._day_log)
        all_events.extend(self._night_log)
        all_events.extend(self._observer_log)
        all_events.extend(self._private_events)
        seen_ids: set[int] = set()
        unique: list[GameEvent] = []
        for e in sorted(all_events, key=lambda x: x.event_id):
            if e.event_id not in seen_ids:
                seen_ids.add(e.event_id)
                unique.append(e)
        result = [e for e in unique if e.event_id > after_event_id]
        if visibility:
            result = [e for e in result if visibility in e.visibility or visibility == "all"]
        return result
