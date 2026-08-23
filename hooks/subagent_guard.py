#!/usr/bin/env python3
"""Guard model-driven interruption of subagents."""

from __future__ import annotations

import json
import sys
from typing import Any

USER_INTERRUPT_PREFIX = "USER_REQUESTED_INTERRUPT:"
ORCHESTRATOR_CORRECTION_PREFIX = "ORCHESTRATOR_CORRECTION:"
CORRECTION_REASONS = frozenset(
    {"wrong_model", "wrong_role", "descendant_orchestration", "scope_drift"}
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
    return "send_input" if value.endswith("send_input") else ""


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
    if payload.get("hook_event_name") == "PreToolUse":
        result = _pre_tool_use(payload)
    else:
        result: dict[str, object] = {}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
