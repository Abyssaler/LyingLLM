from __future__ import annotations

from typing import Any, Optional


class ConversationManager:
    def __init__(self, max_messages: int = 100) -> None:
        self._messages: list[dict[str, str]] = []
        self._max_messages: int = max_messages

    def add_system(self, content: str) -> None:
        self._messages.insert(0, {"role": "system", "content": content})

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._trim()

    def get_messages(
        self,
        include_system: bool = True,
        last_n: Optional[int] = None,
    ) -> list[dict[str, str]]:
        messages = list(self._messages)
        if not include_system:
            messages = [m for m in messages if m["role"] != "system"]
        if last_n is not None:
            system_msgs = [m for m in messages if m["role"] == "system"]
            non_system = [m for m in messages if m["role"] != "system"]
            non_system = non_system[-last_n:]
            messages = system_msgs + non_system
        return messages

    def get_context_window(self, max_tokens: int = 4000, tokens_per_msg: int = 100) -> list[dict[str, str]]:
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        non_system = [m for m in self._messages if m["role"] != "system"]
        budget = max_tokens - len(system_msgs) * tokens_per_msg
        if budget < 0:
            return system_msgs
        selected: list[dict[str, str]] = []
        remaining = budget
        for msg in reversed(non_system):
            if remaining <= 0:
                break
            selected.insert(0, msg)
            remaining -= tokens_per_msg
        return system_msgs + selected

    def clear_conversation(self) -> None:
        self._messages = [m for m in self._messages if m["role"] == "system"]

    def clear_all(self) -> None:
        self._messages.clear()

    def replace_system(self, content: str) -> None:
        self._messages = [m for m in self._messages if m["role"] != "system"]
        self._messages.insert(0, {"role": "system", "content": content})

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def has_system(self) -> bool:
        return any(m["role"] == "system" for m in self._messages)

    def _trim(self) -> None:
        if len(self._messages) <= self._max_messages:
            return
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        non_system = [m for m in self._messages if m["role"] != "system"]
        keep_count = self._max_messages - len(system_msgs)
        if keep_count > 0:
            non_system = non_system[-keep_count:]
        self._messages = system_msgs + non_system

    def to_dict(self) -> list[dict[str, str]]:
        return list(self._messages)

    @classmethod
    def from_dict(cls, data: list[dict[str, str]]) -> ConversationManager:
        cm = cls()
        cm._messages = list(data)
        return cm