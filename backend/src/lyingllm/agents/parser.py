"""Parse agent JSON outputs into structured actions.

The parser is intentionally strict: it only accepts structured JSON and
refuses to "guess" an action from natural language.
"""

from __future__ import annotations

import json
from typing import Any

from lyingllm.domain.models.action import action_from_dict


def parse_action(raw: str | dict[str, Any]) -> Any:
    """Parse a raw string or dict into an action object.

    Raises ``ValueError`` on any failure so the engine can retry.
    """
    if isinstance(raw, str):
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        data = json.loads(text)
    else:
        data = raw

    if not isinstance(data, dict):
        raise ValueError("Action must be a JSON object")

    action_type = data.get("action")
    if not action_type:
        raise ValueError("Missing 'action' field")

    return action_from_dict(data)
