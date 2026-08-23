#!/usr/bin/env python3
"""Inject a lightweight orchestration reminder for the main agent."""

from __future__ import annotations

import json

CONTEXT = (
    "Main agent: load codex-orchestration when delegation has a clear payoff; "
    "apply its review gate before code delivery. Keep simple work local. "
    "Wait before decisions, writes, or final answers that pending agents could change; "
    "otherwise continue only independent, non-overlapping work. Use a direct call for each "
    "subagent lifecycle tool when available. If the host exposes them only through functions.exec, "
    "make exactly one lifecycle call per program and return its result unchanged. A wait "
    "releases only target IDs explicitly "
    "mapped to completed, errored, interrupted, shutdown, or not_found; timed_out=true, "
    "empty or missing status, and omitted target entries stay pending and require another wait. "
    "Summarize only after all requested results arrive. Classify every send_input by delivery "
    "time. Guidance for a running agent that can affect the current work, including FOCUS or "
    "DELTA, uses ORCHESTRATOR_GUIDANCE: and interrupt=true so it is handled immediately instead "
    "of entering the queue. interrupt=true redirects the current task; close_agent is a separate "
    "operation. Queue only input deliberately intended after the current task, using "
    "AFTER_CURRENT_TASK: with explicit interrupt=false. After an explicit user stop or "
    "replacement request, use USER_REQUESTED_INTERRUPT: with interrupt=true. Put a delivery "
    "prefix exactly once on the first non-empty line of the sole text carrier, followed by "
    "non-empty visible input. After any accepted send_input, keep the target pending and wait "
    "for a later terminal result; never reuse an earlier terminal status. "
    "The main agent closes an agent only after wait_agent reports a "
    "terminal status; the guard does not enforce close ordering. Derived agents ignore "
    "this reminder."
)


def main() -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": CONTEXT,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
