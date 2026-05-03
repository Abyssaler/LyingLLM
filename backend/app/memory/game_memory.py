from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MemoryVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    FACTION = "faction"


@dataclass
class MemoryEntry:
    round: int
    phase: str
    event_type: str
    content: str
    visibility: MemoryVisibility = MemoryVisibility.PUBLIC
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


class GameMemory:
    def __init__(self) -> None:
        self._public: list[MemoryEntry] = []
        self._private: list[MemoryEntry] = []
        self._faction: list[MemoryEntry] = []
        self._round: int = 0

    def set_round(self, round_num: int) -> None:
        self._round = round_num

    def add_public(self, phase: str, event_type: str, content: str, **metadata: Any) -> MemoryEntry:
        entry = MemoryEntry(
            round=self._round,
            phase=phase,
            event_type=event_type,
            content=content,
            visibility=MemoryVisibility.PUBLIC,
            metadata=metadata,
        )
        self._public.append(entry)
        return entry

    def add_private(self, phase: str, event_type: str, content: str, **metadata: Any) -> MemoryEntry:
        entry = MemoryEntry(
            round=self._round,
            phase=phase,
            event_type=event_type,
            content=content,
            visibility=MemoryVisibility.PRIVATE,
            metadata=metadata,
        )
        self._private.append(entry)
        return entry

    def add_faction(self, phase: str, event_type: str, content: str, **metadata: Any) -> MemoryEntry:
        entry = MemoryEntry(
            round=self._round,
            phase=phase,
            event_type=event_type,
            content=content,
            visibility=MemoryVisibility.FACTION,
            metadata=metadata,
        )
        self._faction.append(entry)
        return entry

    def get_public(self, round_num: Optional[int] = None) -> list[MemoryEntry]:
        if round_num is None:
            return list(self._public)
        return [e for e in self._public if e.round == round_num]

    def get_private(self, round_num: Optional[int] = None) -> list[MemoryEntry]:
        if round_num is None:
            return list(self._private)
        return [e for e in self._private if e.round == round_num]

    def get_faction(self, round_num: Optional[int] = None) -> list[MemoryEntry]:
        if round_num is None:
            return list(self._faction)
        return [e for e in self._faction if e.round == round_num]

    def get_visible_for(self, include_faction: bool = False) -> list[MemoryEntry]:
        entries = list(self._public) + list(self._private)
        if include_faction:
            entries += list(self._faction)
        entries.sort(key=lambda e: (e.round, e.phase))
        return entries

    def get_context_for_agent(self, include_faction: bool = False, max_rounds: Optional[int] = None) -> str:
        entries = self.get_visible_for(include_faction=include_faction)
        if max_rounds is not None:
            min_round = max(0, self._round - max_rounds + 1)
            entries = [e for e in entries if e.round >= min_round]
        if not entries:
            return "暂无已知信息。"
        lines: list[str] = []
        current_round = -1
        for entry in entries:
            if entry.round != current_round:
                current_round = entry.round
                lines.append(f"\n--- 第{current_round}轮 ---")
            vis_tag = ""
            if entry.visibility == MemoryVisibility.PRIVATE:
                vis_tag = "[私有]"
            elif entry.visibility == MemoryVisibility.FACTION:
                vis_tag = "[阵营]"
            lines.append(f"({entry.phase}/{entry.event_type}) {vis_tag}{entry.content}")
        return "\n".join(lines)

    def compress(self, strategy: str = "summarize", threshold_rounds: int = 5) -> None:
        if self._round <= threshold_rounds:
            return
        if strategy == "summarize":
            self._compress_summarize(threshold_rounds)
        elif strategy == "sliding_window":
            self._compress_sliding_window(threshold_rounds)

    def _compress_summarize(self, threshold_rounds: int) -> None:
        old_public = [e for e in self._public if e.round < self._round - threshold_rounds]
        recent_public = [e for e in self._public if e.round >= self._round - threshold_rounds]
        if old_public:
            summary_parts = [f"第{e.round}轮({e.phase}): {e.content}" for e in old_public]
            summary = MemoryEntry(
                round=0,
                phase="summary",
                event_type="memory_compressed",
                content="历史摘要: " + "; ".join(summary_parts),
                visibility=MemoryVisibility.PUBLIC,
            )
            self._public = [summary] + recent_public
        old_private = [e for e in self._private if e.round < self._round - threshold_rounds]
        recent_private = [e for e in self._private if e.round >= self._round - threshold_rounds]
        if old_private:
            summary_parts = [f"第{e.round}轮({e.phase}): {e.content}" for e in old_private]
            summary = MemoryEntry(
                round=0,
                phase="summary",
                event_type="memory_compressed",
                content="私有记忆摘要: " + "; ".join(summary_parts),
                visibility=MemoryVisibility.PRIVATE,
            )
            self._private = [summary] + recent_private
        old_faction = [e for e in self._faction if e.round < self._round - threshold_rounds]
        recent_faction = [e for e in self._faction if e.round >= self._round - threshold_rounds]
        if old_faction:
            summary_parts = [f"第{e.round}轮({e.phase}): {e.content}" for e in old_faction]
            summary = MemoryEntry(
                round=0,
                phase="summary",
                event_type="memory_compressed",
                content="阵营记忆摘要: " + "; ".join(summary_parts),
                visibility=MemoryVisibility.FACTION,
            )
            self._faction = [summary] + recent_faction

    def _compress_sliding_window(self, threshold_rounds: int) -> None:
        min_round = self._round - threshold_rounds
        self._public = [e for e in self._public if e.round >= min_round]
        self._private = [e for e in self._private if e.round >= min_round]
        self._faction = [e for e in self._faction if e.round >= min_round]

    def to_dict(self) -> dict[str, Any]:
        def _entries_to_list(entries: list[MemoryEntry]) -> list[dict[str, Any]]:
            return [
                {
                    "round": e.round,
                    "phase": e.phase,
                    "event_type": e.event_type,
                    "content": e.content,
                    "visibility": e.visibility.value,
                    "metadata": e.metadata,
                }
                for e in entries
            ]

        return {
            "public": _entries_to_list(self._public),
            "private": _entries_to_list(self._private),
            "faction": _entries_to_list(self._faction),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameMemory:
        mem = cls()

        def _list_to_entries(items: list[dict[str, Any]]) -> list[MemoryEntry]:
            return [
                MemoryEntry(
                    round=item["round"],
                    phase=item["phase"],
                    event_type=item["event_type"],
                    content=item["content"],
                    visibility=MemoryVisibility(item.get("visibility", "public")),
                    metadata=item.get("metadata", {}),
                )
                for item in items
            ]

        mem._public = _list_to_entries(data.get("public", []))
        mem._private = _list_to_entries(data.get("private", []))
        mem._faction = _list_to_entries(data.get("faction", []))
        return mem