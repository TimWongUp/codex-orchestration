# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`. `subagent_scope.py` tells derived agents whether they are read-only or a lease-gated worker.

Hooks are optional during the Agent-driven procedure in `INSTALL.md`. The Agent copies both scripts, shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and preserves unrelated hook groups. Runtime validation checks them only when explicitly invoked with `--hooks`. Hook text never grants a write lease.

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
