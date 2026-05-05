"""Role assignment helpers.

Uses ``rule.md`` §1.1 fixed counts and shuffles randomly.
"""

from __future__ import annotations

import random

from lyingllm.domain.models.player import Player, RoleId
from lyingllm.domain.rules.constants import ROLE_COUNTS


def assign_roles(
    *,
    rng: random.Random | None = None,
) -> list[RoleId]:
    """Return a shuffled list of 12 RoleIds matching ``ROLE_COUNTS``."""
    roles: list[RoleId] = []
    for role_name, count in ROLE_COUNTS.items():
        role = RoleId(role_name)
        roles.extend([role] * count)
    r = rng or random.Random()
    r.shuffle(roles)
    return roles
