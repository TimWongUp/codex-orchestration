#!/usr/bin/env python3
"""Inject role-aware scope reminders for spawned Codex subagents."""

from __future__ import annotations

import json
import sys

WRITER_ROLES = frozenset({"worker", "diagnosing-bugs-worker", "prototype-worker"})

COMMON = """\
You are a derived agent, not the main orchestrator.
Do not create, coordinate, wait for, or manage descendants.
Complete only the assigned task and return the result to the main agent.
"""

WRITER = """\
You are a writable worker. This hook does not grant a write lease.
Write only when the main-agent task message explicitly grants the WRITE LEASE
and includes BRANCH, ALLOWED PATHS, VALIDATION, and ROUND.
Otherwise return blocked. Do not perform Git operations or external writes.
"""

READ_ONLY = """\
You are read-only. Do not modify files or external state.
Return evidence, analysis, design guidance, or review findings.
"""


def context_for(agent_type: str) -> str:
    boundary = WRITER if agent_type in WRITER_ROLES else READ_ONLY
    return f"{COMMON}\n{boundary}"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
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
