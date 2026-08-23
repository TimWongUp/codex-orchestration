#!/usr/bin/env python3
"""Guard subagent interruption and clarify non-terminal wait results."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from typing import Any

USER_INTERRUPT_PREFIX = "USER_REQUESTED_INTERRUPT:"
ORCHESTRATOR_CORRECTION_PREFIX = "ORCHESTRATOR_CORRECTION:"
CONTROL_PREFIXES = (USER_INTERRUPT_PREFIX, ORCHESTRATOR_CORRECTION_PREFIX)
CORRECTION_REASONS = frozenset(
    {"wrong_model", "wrong_role", "descendant_orchestration", "scope_drift"}
)
TERMINAL_STATES = frozenset({"completed", "errored", "interrupted", "shutdown", "not_found"})
WAIT_RESULT_CONTEXT = (
    "WAIT RESULT CHECK: Keep every target without an explicit terminal status "
    "in the pending set. timed_out=true, an empty or missing status map, an omitted "
    "target entry, and an unrecognized status are non-terminal. Wait again in a later "
    "model-visible operation. close_agent is eligible only for target IDs explicitly mapped to "
    "completed, errored, interrupted, shutdown, or not_found."
)


def _read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _tool_kind(value: object) -> str:
    if not isinstance(value, str):
        return ""
    for kind in ("send_input", "wait_agent"):
        if value.endswith(kind):
            return kind
    return ""


def _walk_json(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)
    elif isinstance(value, str):
        stripped = value.strip()
        candidates = [stripped, *(line.strip() for line in stripped.splitlines())]
        for candidate in candidates:
            if not candidate.startswith(("{", "[")):
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            yield from _walk_json(parsed)


def _terminal_status(value: object) -> bool:
    if isinstance(value, str):
        return value in TERMINAL_STATES
    if isinstance(value, dict):
        return any(state in value for state in TERMINAL_STATES)
    return False


def _requested_agent_ids(payload: dict[str, Any]) -> set[str]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return set()
    targets = tool_input.get("targets")
    if not isinstance(targets, list):
        targets = tool_input.get("ids")
    if not isinstance(targets, list):
        return set()
    return {agent_id for agent_id in targets if isinstance(agent_id, str)}


def _wait_result(payload: dict[str, Any]) -> tuple[dict[str, object], bool] | None:
    for value in _walk_json(payload.get("tool_response")):
        if not isinstance(value, dict):
            continue
        statuses = value.get("status")
        timed_out = value.get("timed_out")
        if isinstance(statuses, dict) and isinstance(timed_out, bool):
            return statuses, timed_out
    return None


def _wait_is_terminal(payload: dict[str, Any]) -> bool:
    result = _wait_result(payload)
    if result is None:
        return False
    statuses, timed_out = result
    if timed_out:
        return False
    requested = _requested_agent_ids(payload)
    if requested:
        return all(
            agent_id in statuses and _terminal_status(statuses[agent_id]) for agent_id in requested
        )
    return bool(statuses) and all(_terminal_status(status) for status in statuses.values())


def _post_wait(payload: dict[str, Any]) -> dict[str, object]:
    if _wait_is_terminal(payload):
        return {}
    return _wait_context()


def _wait_context() -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": WAIT_RESULT_CONTEXT,
        }
    }


def _text_control_kind(value: str) -> str:
    text = value.lstrip()
    control_count = sum(value.count(prefix) for prefix in CONTROL_PREFIXES)
    if control_count == 0:
        return "ordinary"
    if control_count != 1 or not text.startswith(CONTROL_PREFIXES):
        return "invalid"
    if text.startswith(USER_INTERRUPT_PREFIX):
        return "authorized"
    remainder = text[len(ORCHESTRATOR_CORRECTION_PREFIX) :].lstrip()
    reason = remainder.split(maxsplit=1)[0] if remainder else ""
    return "authorized" if reason in CORRECTION_REASONS else "invalid"


def _control_kind(tool_input: dict[str, Any]) -> str:
    kinds: list[str] = []
    message = tool_input.get("message")
    if isinstance(message, str):
        kinds.append(_text_control_kind(message))
    items = tool_input.get("items")
    if isinstance(items, list):
        kinds.extend(
            _text_control_kind(item["text"])
            for item in items
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        )
    control_kinds = [kind for kind in kinds if kind != "ordinary"]
    if "invalid" in control_kinds or len(control_kinds) > 1:
        return "invalid"
    if control_kinds and len(kinds) > 1:
        return "invalid"
    if control_kinds:
        return "authorized"
    return "ordinary"


def _input_shape_error(tool_input: object) -> str | None:
    if not isinstance(tool_input, dict):
        return "send_input tool_input must be an object."
    has_message = "message" in tool_input
    has_items = "items" in tool_input
    if has_message == has_items:
        return "send_input must use exactly one of message or items."
    if has_message:
        if not isinstance(tool_input["message"], str):
            return "send_input message must be a string."
        return None
    items = tool_input["items"]
    if not isinstance(items, list) or not items:
        return "send_input items must be a non-empty list."
    for item in items:
        if not isinstance(item, dict):
            return "Each send_input item must be an object."
        if "type" in item and not isinstance(item["type"], str):
            return "Each send_input item type field must be a string."
        if "text" in item:
            if item.get("type") != "text":
                return "A send_input text field is valid only on an item with type text."
            if not isinstance(item["text"], str):
                return "Each send_input item text field must be a string."
        if item.get("type") == "text" and "text" not in item:
            return "A text send_input item requires a text field."
    return None


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _pre_tool_use(payload: dict[str, Any]) -> dict[str, object]:
    if _tool_kind(payload.get("tool_name")) != "send_input":
        return {}
    tool_input = payload.get("tool_input")
    shape_error = _input_shape_error(tool_input)
    if shape_error is not None:
        return _deny(shape_error)
    assert isinstance(tool_input, dict)
    arguments = tool_input
    interrupt = arguments.get("interrupt")
    if "interrupt" in arguments and interrupt is not False and interrupt is not True:
        return _deny("interrupt must be false for queued input or true with an authorized prefix.")
    control_kind = _control_kind(arguments)
    if control_kind == "invalid":
        return _deny(
            "A control prefix must appear exactly once and begin the first non-empty line of "
            "the sole text carrier. "
            "ORCHESTRATOR_CORRECTION: also requires one reason code: wrong_model, wrong_role, "
            "descendant_orchestration, or scope_drift."
        )
    if control_kind == "authorized" and interrupt is not True:
        return _deny(
            "A control-prefixed send_input requires interrupt=true for immediate redirection. "
            "Remove the control prefix and use interrupt=false only for an ordinary queued "
            "follow-up."
        )
    if interrupt is True and control_kind == "ordinary":
        return _deny(
            "Keep the running agent. Queue ordinary follow-up input with interrupt=false. "
            "Use USER_REQUESTED_INTERRUPT: only after an explicit user stop or replacement "
            "request. ORCHESTRATOR_CORRECTION: requires one reason code: wrong_model, "
            "wrong_role, descendant_orchestration, or scope_drift."
        )
    return {}


def main() -> int:
    payload = _read_payload()
    event = payload.get("hook_event_name")
    tool_kind = _tool_kind(payload.get("tool_name"))
    if event == "PostToolUse" and tool_kind == "wait_agent":
        result = _post_wait(payload)
    elif event == "PreToolUse":
        result = _pre_tool_use(payload)
    else:
        result: dict[str, object] = {}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
