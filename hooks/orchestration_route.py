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
    "Summarize only after all requested results arrive. "
    "Queue ordinary follow-ups with interrupt=false. After an explicit user stop or replacement "
    "request, put USER_REQUESTED_INTERRUPT: exactly once on the first non-empty line of the sole "
    "text carrier and set interrupt=true. With direct evidence of wrong "
    "model, wrong role, forbidden descendant orchestration, or clear scope drift, a bounded "
    "immediate correction may use ORCHESTRATOR_CORRECTION: plus the matching closed reason "
    "code in that same envelope and must set interrupt=true; the guard rejects a control-prefixed "
    "message that would otherwise queue. A correction interrupt may terminate the agent; it is "
    "not arbitrary stop authority. "
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
