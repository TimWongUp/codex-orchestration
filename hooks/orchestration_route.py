#!/usr/bin/env python3
"""Inject a lightweight orchestration reminder for the main agent."""

from __future__ import annotations

import json

CONTEXT = (
    "Main agent: load codex-orchestration when delegation has a clear payoff; "
    "apply its review gate before code delivery. Keep simple work local. "
    "Wait before decisions, writes, or final answers that pending agents could change; "
    "otherwise continue only independent, non-overlapping work. If a wait times out, "
    "keep waiting later and summarize only after all requested results arrive. "
    "Queue follow-ups with interrupt=false. Use USER_REQUESTED_INTERRUPT: only after "
    "an explicit user stop or replacement request, and close an agent only after "
    "wait_agent reports a terminal status. "
    "Derived agents ignore this reminder."
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
