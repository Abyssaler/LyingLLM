from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


class ParseError(Exception):
    def __init__(self, message: str, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


class ValidationError(Exception):
    def __init__(self, message: str, action: Optional[dict] = None) -> None:
        super().__init__(message)
        self.action = action


@dataclass
class ParsedOutput:
    thinking: Optional[str] = None
    action: Optional[dict[str, Any]] = None
    speech: Optional[str] = None
    death_skill: Optional[dict[str, Any]] = None
    sheriff_transfer: Optional[dict[str, Any]] = None
    last_words: Optional[str] = None
    raw: str = ""


class OutputParser:
    def parse(self, raw: str) -> ParsedOutput:
        if not raw or not raw.strip():
            raise ParseError("Empty output from LLM", raw)

        json_str = self._extract_json(raw)
        if json_str is None:
            raise ParseError(f"Could not extract JSON from LLM output", raw)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON: {e}", raw)

        if not isinstance(data, dict):
            raise ParseError(f"Expected JSON object, got {type(data).__name__}", raw)

        return ParsedOutput(
            thinking=data.get("thinking"),
            action=data.get("action"),
            speech=data.get("speech"),
            death_skill=data.get("death_skill"),
            sheriff_transfer=data.get("sheriff_transfer"),
            last_words=data.get("last_words"),
            raw=raw,
        )

    def _extract_json(self, text: str) -> Optional[str]:
        json_pattern = re.compile(r'```(?:json)?\s*\n?(.*?)\n?\s*```', re.DOTALL)
        match = json_pattern.search(text)
        if match:
            return match.group(1).strip()

        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            return text[brace_start:brace_end + 1]

        bracket_start = text.find('[')
        bracket_end = text.rfind(']')
        if bracket_start != -1 and bracket_end > bracket_start:
            return text[bracket_start:bracket_end + 1]

        return None


class ActionValidator:
    def validate(
        self,
        parsed: ParsedOutput,
        alive_player_ids: list[int],
        allowed_action_types: Optional[list[str]] = None,
        current_phase: str = "",
    ) -> ParsedOutput:
        if parsed.action is not None:
            parsed.action = self._validate_action(
                parsed.action, alive_player_ids, allowed_action_types
            )
        if parsed.death_skill is not None:
            parsed.death_skill = self._validate_death_skill(
                parsed.death_skill, alive_player_ids
            )
        if parsed.sheriff_transfer is not None:
            parsed.sheriff_transfer = self._validate_sheriff_transfer(
                parsed.sheriff_transfer, alive_player_ids
            )
        return parsed

    def _validate_action(
        self,
        action: dict[str, Any],
        alive_player_ids: list[int],
        allowed_action_types: Optional[list[str]],
    ) -> dict[str, Any]:
        if not isinstance(action, dict):
            raise ValidationError(f"Action must be a dict, got {type(action).__name__}", action)
        action_type = action.get("type")
        if action_type is None:
            raise ValidationError("Action missing 'type' field", action)
        if allowed_action_types and action_type not in allowed_action_types:
            raise ValidationError(
                f"Action type '{action_type}' not allowed. Allowed: {allowed_action_types}", action
            )
        target = action.get("target")
        if target is not None:
            if not isinstance(target, int):
                raise ValidationError(f"Action target must be int, got {type(target).__name__}", action)
            if target not in alive_player_ids:
                raise ValidationError(
                    f"Target player {target} is not alive. Alive: {alive_player_ids}", action
                )
        return action

    def _validate_death_skill(
        self, death_skill: dict[str, Any], alive_player_ids: list[int]
    ) -> dict[str, Any]:
        if not isinstance(death_skill, dict):
            raise ValidationError(f"death_skill must be a dict, got {type(death_skill).__name__}", death_skill)
        target = death_skill.get("target")
        if target is not None:
            if not isinstance(target, int):
                raise ValidationError(f"death_skill target must be int", death_skill)
            if target not in alive_player_ids:
                raise ValidationError(
                    f"death_skill target {target} is not alive", death_skill
                )
        return death_skill

    def _validate_sheriff_transfer(
        self, sheriff_transfer: dict[str, Any], alive_player_ids: list[int]
    ) -> dict[str, Any]:
        if not isinstance(sheriff_transfer, dict):
            raise ValidationError(
                f"sheriff_transfer must be a dict, got {type(sheriff_transfer).__name__}",
                sheriff_transfer,
            )
        target = sheriff_transfer.get("target")
        if target is None:
            raise ValidationError("sheriff_transfer requires a 'target' field", sheriff_transfer)
        if not isinstance(target, int):
            raise ValidationError("sheriff_transfer target must be int", sheriff_transfer)
        if target not in alive_player_ids:
            raise ValidationError(
                f"sheriff_transfer target {target} is not alive. Alive: {alive_player_ids}",
                sheriff_transfer,
            )
        return sheriff_transfer