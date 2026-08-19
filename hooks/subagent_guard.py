#!/usr/bin/env python3
"""Guard model-driven interruption and premature closure of subagents."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

USER_INTERRUPT_PREFIX = "USER_REQUESTED_INTERRUPT:"
TERMINAL_STATES = frozenset({"interrupted", "shutdown", "not_found"})


def _read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _tool_kind(value: object) -> str:
    if not isinstance(value, str):
        return ""
    for kind in ("send_input", "wait_agent", "close_agent"):
        if value.endswith(kind):
            return kind
    return ""


def _state_root() -> Path:
    override = os.environ.get("CODEX_ORCHESTRATION_STATE_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "codex-orchestration-subagents"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _marker(session_id: str, agent_id: str) -> Path:
    return _state_root() / _digest(session_id) / f"{_digest(agent_id)}.terminal"


def _mark_terminal(session_id: str, agent_id: str) -> None:
    if not session_id or not agent_id:
        return
    target = _marker(session_id, agent_id)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("terminal\n", encoding="utf-8")
    except OSError:
        return


def _clear_terminal(session_id: str, agent_id: str) -> None:
    if not session_id or not agent_id:
        return
    try:
        _marker(session_id, agent_id).unlink(missing_ok=True)
    except OSError:
        return


def _terminal_observed(session_id: str, agent_id: str) -> bool:
    return bool(session_id and agent_id and _marker(session_id, agent_id).is_file())


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
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return
            yield from _walk_json(parsed)


def _is_terminal(value: object) -> bool:
    if isinstance(value, str):
        return value in TERMINAL_STATES
    if isinstance(value, dict):
        return "completed" in value or "errored" in value
    return False


def _record_wait_result(payload: dict[str, Any]) -> None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        return
    for value in _walk_json(payload.get("tool_response")):
        if not isinstance(value, dict):
            continue
        statuses = value.get("status")
        if not isinstance(statuses, dict):
            continue
        for agent_id, status in statuses.items():
            if isinstance(agent_id, str) and _is_terminal(status):
                _mark_terminal(session_id, agent_id)


def _interrupt_authorized(tool_input: dict[str, Any]) -> bool:
    message = tool_input.get("message")
    if isinstance(message, str) and message.lstrip().startswith(USER_INTERRUPT_PREFIX):
        return True
    items = tool_input.get("items")
    if not isinstance(items, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and item["text"].lstrip().startswith(USER_INTERRUPT_PREFIX)
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
    tool_kind = _tool_kind(payload.get("tool_name"))
    tool_input = payload.get("tool_input")
    arguments = tool_input if isinstance(tool_input, dict) else {}

    if tool_kind == "send_input":
        interrupt = arguments.get("interrupt")
        if (
            interrupt is not None
            and interrupt is not False
            and not _interrupt_authorized(arguments)
        ):
            return _deny(
                "Keep the running agent. Queue follow-up input with interrupt=false and continue "
                "non-overlapping work. Use USER_REQUESTED_INTERRUPT: only after an explicit user "
                "request to stop or replace this agent."
            )
        session_id = payload.get("session_id")
        target = arguments.get("target")
        if isinstance(session_id, str) and isinstance(target, str):
            _clear_terminal(session_id, target)

    if tool_kind == "close_agent":
        session_id = payload.get("session_id")
        target = arguments.get("target")
        if not (
            isinstance(session_id, str)
            and isinstance(target, str)
            and _terminal_observed(session_id, target)
        ):
            return _deny(
                "No terminal status has been observed for this agent. Wait for wait_agent to "
                "return completed, errored, interrupted, shutdown, or not_found before closing it; "
                "a wait timeout is not terminal."
            )

    return {}


def main() -> int:
    payload = _read_payload()
    event = payload.get("hook_event_name")
    if event == "PostToolUse" and _tool_kind(payload.get("tool_name")) == "wait_agent":
        _record_wait_result(payload)
        result: dict[str, object] = {}
    elif event == "PreToolUse":
        result = _pre_tool_use(payload)
    else:
        result = {}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
