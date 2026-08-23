# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`: wait before decisions, writes, or final answers that pending agents could change; otherwise continue only independent, non-overlapping work. It keeps each lifecycle call as a separate model-visible operation: direct when the host exposes it, or one call per `functions.exec` program with the result returned unchanged. Timed-out, empty, missing, and partial wait results stay pending, and consolidation waits until every requested target has its own terminal status entry. `subagent_scope.py` tells derived agents whether they are read-only or a lease-gated worker.

`subagent_guard.py` is a narrow, stateless tool guard. Its `PreToolUse` registration denies `send_input` with `interrupt=true` unless the message or item text begins with `USER_REQUESTED_INTERRUPT:` or `ORCHESTRATOR_CORRECTION: <reason_code>`. The first is reserved for an explicit user stop or replacement request. The second accepts only `wrong_model`, `wrong_role`, `descendant_orchestration`, or `scope_drift`; direct evidence and bounded use remain main-agent responsibilities. A correction interrupt may terminate the agent and is not general stop authority. Ordinary follow-ups use `interrupt=false`. Its `PostToolUse` matcher covers direct `wait_agent` calls only. When the host surfaces such an event, the guard adds advisory context for `timed_out=true`, empty or missing status, omitted targets, and unrecognized status. Nested waits may not produce that event, so the Skill and routing reminder remain authoritative. The guard stores no terminal marker and does not register `functions.exec` or `close_agent`; the Skill still requires the main agent to close only targets with explicit terminal entries. Codex flattens namespaced local function names by concatenating, so the matchers and guard normalize the stable function-name suffix. The guard does not decide whether delegation was appropriate or whether a result is correct.

Hooks are optional during the Agent-driven procedure in `INSTALL.md`. The Agent copies all three scripts, shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and preserves unrelated hook groups. Runtime validation checks them only when explicitly invoked with `--hooks`. Hook text never grants a write lease.

These three scripts are owned and released with `codex-orchestration`; they are not shared Hook Runtime source. A machine may register shared context, memory-routing, or closeout Hooks from another repository alongside them. Private composition records that coexistence, while installation and updates continue to merge registrations without replacing unrelated sources. Updating this suite replaces its direct-wait PostToolUse behavior with the stateless advisory, removes old `functions.exec`, `close_agent`, or combined matcher registrations, and preserves unrelated registrations.

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
