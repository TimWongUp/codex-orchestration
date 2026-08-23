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
    "make exactly one lifecycle call per program and return its result unchanged. Ordinary "
    'spawn_agent calls explicitly use fork_turns="none" for fresh context. A positive value '
    "carries bounded partial history and may combine model overrides. Omitting fork_turns or using "
    '"all" creates a full-history fork that inherits the parent model and reasoning effort and '
    "cannot combine those overrides. "
    "Use send_message for supplemental information that does not change the assigned task; it "
    "never starts a turn. Use followup_task for genuine later or corrective work: a running target "
    "receives it at the next message boundary or after a pending tool call, while an idle target "
    "starts its next turn. wait_agent waits "
    "for the caller's mailbox, while "
    "list_agents and final notifications reconcile the current tree and statuses. "
    "After followup_task, earlier final notifications and snapshots for that target are stale. "
    "interrupt_agent interrupts an active turn while preserving context. Do not infer completion "
    "from a missing wait update or an old status snapshot. A third writable round creates a new "
    "agent rather than closing an old thread. On an explicit stop, create no new work, interrupt "
    "active descendants, and wait for a fresh converged status. Derived agents ignore this "
    "reminder."
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
