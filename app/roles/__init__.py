from app.roles.base import BaseRole, ActionResult, GameContext
from app.roles.werewolf import Werewolf
from app.roles.villager import Villager
from app.roles.seer import Seer
from app.roles.witch import Witch
from app.roles.hunter import Hunter
from app.roles.guard import Guard

ROLE_REGISTRY: dict[str, type[BaseRole]] = {
    "werewolf": Werewolf,
    "villager": Villager,
    "seer": Seer,
    "witch": Witch,
    "hunter": Hunter,
    "guard": Guard,
}


def create_role(role_key: str) -> BaseRole:
    role_cls = ROLE_REGISTRY.get(role_key)
    if role_cls is None:
        raise ValueError(f"Unknown role: {role_key}")
    if hasattr(role_cls, "DEFAULT_CONFIG"):
        return role_cls(role_cls.DEFAULT_CONFIG)
    raise ValueError(f"Role {role_key} has no DEFAULT_CONFIG")


__all__ = [
    "BaseRole", "ActionResult", "GameContext",
    "Werewolf", "Villager", "Seer", "Witch", "Hunter", "Guard",
    "ROLE_REGISTRY", "create_role",
]