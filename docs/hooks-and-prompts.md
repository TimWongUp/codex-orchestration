# Hooks and long-lived prompts

## Optional hooks

`subagent_scope.py` injects one high-priority check only for writable worker roles: a complete
canonical lease package must be present before writing. Read-only agents receive no extra Hook
context because their identity, scope, and panel boundaries already live in Agent profiles.

The Hook is optional during the Agent-driven procedure in `INSTALL.md`. The Agent copies the
script, shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and
preserves unrelated Hook groups. Runtime validation checks it only when explicitly invoked with
`--hooks`. Hook text never grants a write lease.

The former project `UserPromptSubmit` route Hook is retired because the Skill, repository prompt,
and current tool schemas already carry the main-agent policy. A machine may register shared
context, memory-routing, or closeout Hooks from another repository alongside this Hook. Those
registrations and Codex-native agent status notifications remain outside this project's ownership.

## Long-lived main-agent prompt

If a repository or global `AGENTS.md` needs an explicit pointer, use this compact block:

```md
## Subagent orchestration

- Main agent only: load `codex-orchestration` before creating, coordinating, or waiting for subagents.
- The main agent owns Git, acceptance, review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Writable workers require the canonical single-writer lease; derived agents never orchestrate descendants.
```

Keep the full workflow in the Skill. Do not duplicate role lists, task schemas, model routes, or
review rules into every repository prompt.
