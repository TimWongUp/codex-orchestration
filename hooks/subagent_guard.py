#!/usr/bin/env python3
"""Guard subagent interruption and clarify non-terminal wait results."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from typing import Any

USER_INTERRUPT_PREFIX = "USER_REQUESTED_INTERRUPT:"
ORCHESTRATOR_CORRECTION_PREFIX = "ORCHESTRATOR_CORRECTION:"
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


def _text_authorized(value: str) -> bool:
    text = value.lstrip()
    if text.startswith(USER_INTERRUPT_PREFIX):
        return True
    if not text.startswith(ORCHESTRATOR_CORRECTION_PREFIX):
        return False
    remainder = text[len(ORCHESTRATOR_CORRECTION_PREFIX) :].lstrip()
    reason = remainder.split(maxsplit=1)[0] if remainder else ""
    return reason in CORRECTION_REASONS


def _interrupt_authorized(tool_input: dict[str, Any]) -> bool:
    message = tool_input.get("message")
    if isinstance(message, str) and _text_authorized(message):
        return True
    items = tool_input.get("items")
    if not isinstance(items, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and _text_authorized(item["text"])
        for item in items
    )


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
    arguments = tool_input if isinstance(tool_input, dict) else {}
    interrupt = arguments.get("interrupt")
    if interrupt is True and not _interrupt_authorized(arguments):
        return _deny(
            "Keep the running agent. Queue ordinary follow-up input with interrupt=false. "
            "Use USER_REQUESTED_INTERRUPT: only after an explicit user stop or replacement "
            "request. ORCHESTRATOR_CORRECTION: requires one reason code: wrong_model, "
            "wrong_role, descendant_orchestration, or scope_drift."
        )
    if interrupt is not None and interrupt is not False and interrupt is not True:
        return _deny("interrupt must be false for queued input or true with an authorized prefix.")
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
