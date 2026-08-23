# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`: wait before decisions, writes, or final answers that pending agents could change; otherwise continue only independent, non-overlapping work. It also keeps timed-out waits pending and delays consolidation until every requested result reaches a terminal state. `subagent_scope.py` tells derived agents whether they are read-only or a lease-gated worker.

`subagent_guard.py` is a narrow tool guard. Its `PreToolUse` registration denies `send_input` with `interrupt=true` unless the message or item text begins with `USER_REQUESTED_INTERRUPT:` or `ORCHESTRATOR_CORRECTION: <reason_code>`. The first is reserved for an explicit user stop or replacement request. The second accepts only `wrong_model`, `wrong_role`, `descendant_orchestration`, or `scope_drift`; direct evidence and bounded use remain main-agent responsibilities. A correction interrupt may terminate the agent and is not general stop authority. Ordinary follow-ups use `interrupt=false`. The guard does not register `wait_agent` or `close_agent`, and has no terminal-marker enforcement: nested `exec` wait results cannot be reliably associated with later close calls. The Skill still requires the main agent to close only after `wait_agent` reports a terminal status. Codex flattens namespaced local function names by concatenation, so the matcher and guard normalize the stable function-name suffix. The guard does not decide whether delegation was appropriate or whether a result is correct.

Hooks are optional during the Agent-driven procedure in `INSTALL.md`. The Agent copies all three scripts, shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and preserves unrelated hook groups. Runtime validation checks them only when explicitly invoked with `--hooks`. Hook text never grants a write lease.

These three scripts are owned and released with `codex-orchestration`; they are not shared Hook Runtime source. A machine may register shared context, memory-routing, or closeout Hooks from another repository alongside them. Private composition records that coexistence, while installation and updates continue to merge registrations without replacing unrelated sources. Updating this suite removes its old `wait_agent` PostToolUse and `close_agent` matcher registrations while preserving unrelated registrations.

## Long-lived main-agent prompt

If a repository or global `AGENTS.md` needs an explicit pointer, use this compact block:

```md
## Subagent orchestration

- Main agent only: load `codex-orchestration` before creating, coordinating, or waiting for subagents.
- The main agent owns Git, acceptance, review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Writable workers require the canonical single-writer lease; derived agents never orchestrate descendants.
```

Keep the full workflow in the Skill. Do not duplicate role lists, task schemas, model routes, or review rules into every repository prompt.
