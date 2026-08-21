# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`: continue non-overlapping work while agents run, keep timed-out waits pending, and consolidate only after every requested result reaches a terminal state. `subagent_scope.py` tells derived agents whether they are read-only or a lease-gated worker.

`subagent_guard.py` is a narrow tool guard. Its `PreToolUse` registration denies `send_input` with an interrupting value unless the message begins with `USER_REQUESTED_INTERRUPT:`, which the Skill reserves for an explicit user stop or replacement request. It also denies `close_agent` until its `PostToolUse` registration has observed a terminal result for that target from `wait_agent`. Terminal markers are small session-scoped files under the host temporary directory; an empty or timed-out wait records nothing, and a new `send_input` clears the target's old terminal marker. Codex flattens namespaced local function names by concatenation, so the matcher and guard normalize the stable function-name suffix. The guard does not decide whether delegation was appropriate or whether a result is correct.

Hooks are optional during the Agent-driven procedure in `INSTALL.md`. The Agent copies all three scripts, shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and preserves unrelated hook groups. Runtime validation checks them only when explicitly invoked with `--hooks`. Hook text and terminal markers never grant a write lease.

These three scripts are owned and released with `codex-orchestration`; they are not shared Hook Runtime source. A machine may register shared context, memory-routing, or closeout Hooks from another repository alongside them. Private composition records that coexistence, while installation and updates continue to merge registrations without replacing unrelated sources.

## Long-lived main-agent prompt

If a repository or global `AGENTS.md` needs an explicit pointer, use this compact block:

```md
## Subagent orchestration

- Load `codex-orchestration` before creating, coordinating, or waiting for subagents.
- The main agent owns Git, acceptance, review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Writable workers require the canonical single-writer lease; derived agents never orchestrate descendants.
```

Keep the full workflow in the Skill. Do not duplicate role lists, task schemas, model routes, or review rules into every repository prompt.
