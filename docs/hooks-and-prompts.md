# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`. `subagent_scope.py` tells derived agents whether they are read-only or a lease-gated worker.

Install them with:

```bash
python3 scripts/install.py --apply --with-hooks
```

The installer adds namespaced command registrations while preserving unrelated hook groups. Hook text never grants a write lease.

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
