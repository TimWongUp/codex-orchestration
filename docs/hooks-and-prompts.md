# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`: wait before
decisions, writes, or final answers that pending agents could change; otherwise continue only
independent, non-overlapping work. It also restates the v2 lifecycle: ordinary `spawn_agent` uses
`fork_turns="none"`, `send_message` queues supplemental context without starting a turn,
`followup_task` delivers later or corrective work to a running target at its next boundary and
starts a new turn for an idle target, `wait_agent` waits for the caller mailbox,
`interrupt_agent` preserves context while interrupting an active turn, and `list_agents` plus final
notifications reconcile status. `subagent_scope.py` tells derived agents whether they are
read-only or a lease-gated worker.

Hooks are optional during the Agent-driven procedure in `INSTALL.md`. The Agent copies both
scripts, shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and
preserves unrelated Hook groups. Runtime validation checks them only when explicitly invoked with
`--hooks`. Hook text never grants a write lease.

These scripts are owned and released with `codex-orchestration`; they are not shared Hook Runtime
source. A machine may register shared context, memory-routing, or closeout Hooks from another
repository alongside them. Private composition records that coexistence, while installation and
updates continue to merge registrations without replacing unrelated sources.

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
