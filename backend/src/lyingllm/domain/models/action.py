"""Agent action schemas and validation helpers.

All actions produced by LLM agents are parsed into these structures before
being validated by the engine.
"""

from __future__ import annotations

from typing import Any


class GuardAction:
    """Guard night action."""

    action: str = "guard"

    def __init__(self, *, target: int | None) -> None:
        self.target = target

    def to_dict(self) -> dict[str, Any]:
        return {"action": "guard", "target": self.target}


class WolfVoteKillAction:
    """Werewolf faction kill vote."""

    action: str = "wolf_vote_kill"

    def __init__(self, *, target: int, reason: str = "") -> None:
        self.target = target
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {"action": "wolf_vote_kill", "target": self.target, "reason": self.reason}


class WitchAction:
    """Witch night action."""

    action: str = "witch"

    def __init__(
        self,
        *,
        use_save: bool = False,
        poison_target: int | None = None,
    ) -> None:
        self.use_save = use_save
        self.poison_target = poison_target

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": "witch",
            "use_save": self.use_save,
            "poison_target": self.poison_target,
        }


class SeerAction:
    """Seer night action."""

    action: str = "seer"

    def __init__(self, *, target: int) -> None:
        self.target = target

    def to_dict(self) -> dict[str, Any]:
        return {"action": "seer", "target": self.target}


class SpeechAction:
    """Public daytime speech."""

    action: str = "speech"

    def __init__(self, *, content: str) -> None:
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        return {"action": "speech", "content": self.content}


class VoteAction:
    """Vote action (day exile or sheriff election)."""

    action: str = "vote"

    def __init__(self, *, target: int | str) -> None:
        # int = player_id, "abstain" = abstain
        self.target = target

    def to_dict(self) -> dict[str, Any]:
        return {"action": "vote", "target": self.target}


class HunterShootAction:
    """Hunter death-triggered skill."""

    action: str = "hunter_shoot"

    def __init__(self, *, target: int | None) -> None:
        self.target = target

    def to_dict(self) -> dict[str, Any]:
        return {"action": "hunter_shoot", "target": self.target}


class SheriffTransferAction:
    """Sheriff badge transfer on death."""

    action: str = "sheriff_transfer"

    def __init__(self, *, target: int | str) -> None:
        # int = player_id, "tear_badge" = tear badge
        self.target = target

    def to_dict(self) -> dict[str, Any]:
        return {"action": "sheriff_transfer", "target": self.target}


class SelfDestructAction:
    """Werewolf self-destruct (daytime)."""

    action: str = "self_destruct"

    def __init__(self, *, target: int | None) -> None:
        # None for normal werewolf, player_id for white_wolf_king
        self.target = target

    def to_dict(self) -> dict[str, Any]:
        return {"action": "self_destruct", "target": self.target}


# Union-like helper
def action_from_dict(data: dict[str, Any]) -> Any:
    """Parse a raw action dict into the correct action class."""
    action_type = data.get("action")
    if action_type == "guard":
        return GuardAction(target=data.get("target"))
    if action_type == "wolf_vote_kill":
        return WolfVoteKillAction(target=data["target"], reason=data.get("reason", ""))
    if action_type == "witch":
        return WitchAction(
            use_save=data.get("use_save", False),
            poison_target=data.get("poison_target"),
        )
    if action_type == "seer":
        return SeerAction(target=data["target"])
    if action_type == "speech":
        return SpeechAction(content=data.get("content", ""))
    if action_type == "vote":
        return VoteAction(target=data["target"])
    if action_type == "hunter_shoot":
        return HunterShootAction(target=data.get("target"))
    if action_type == "sheriff_transfer":
        return SheriffTransferAction(target=data["target"])
    if action_type == "self_destruct":
        return SelfDestructAction(target=data.get("target"))
    raise ValueError(f"Unknown action type: {action_type}")
