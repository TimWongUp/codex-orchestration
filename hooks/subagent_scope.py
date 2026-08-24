#!/usr/bin/env python3
"""Reinforce write-lease requirements for writable Codex subagents."""

from __future__ import annotations

import json
import sys

WRITER_ROLES = frozenset({"worker", "diagnosing-bugs-worker", "prototype-worker"})

WRITER = """\
WRITER LEASE CHECK (HIGH PRIORITY): This hook does not grant write authority.
Write only when the main-agent task package includes GOAL, SCOPE, CONSTRAINTS,
DONE WHEN, RETURN, WRITE LEASE: granted, ALLOWED PATHS, BRANCH, ROUND, and
VALIDATION. Otherwise return blocked. Modify only ALLOWED PATHS; leave Git and
external writes to the main agent.
"""


def context_for(agent_type: str) -> str:
    return WRITER if agent_type in WRITER_ROLES else ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    agent_type = str(payload.get("agent_type") or payload.get("agentType") or "")
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": context_for(agent_type),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
