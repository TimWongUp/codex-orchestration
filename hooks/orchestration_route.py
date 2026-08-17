#!/usr/bin/env python3
"""Inject a lightweight orchestration reminder for the main agent."""

from __future__ import annotations

import json

CONTEXT = (
    "Main agent: load codex-orchestration when delegation has a clear payoff; "
    "apply its review gate before code delivery. Keep simple work local. "
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
