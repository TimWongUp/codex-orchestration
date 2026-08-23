# Hooks and long-lived prompts

## Optional hooks

`orchestration_route.py` adds a short main-agent reminder on `UserPromptSubmit`: wait before decisions, writes, or final answers that pending agents could change; otherwise continue only independent, non-overlapping work. It keeps each lifecycle call as a separate model-visible operation: direct when the host exposes it, or one call per `functions.exec` program with the result returned unchanged. Timed-out, empty, missing, and partial wait results stay pending, and consolidation waits until every requested target has its own terminal status entry. `subagent_scope.py` tells derived agents whether they are read-only or a lease-gated worker.

`subagent_guard.py` is a narrow, stateless tool guard. Its `PreToolUse` registration requires every `send_input` call to declare delivery timing with exactly one envelope. `ORCHESTRATOR_GUIDANCE:` carries guidance that can affect current work and requires `interrupt=true`; `AFTER_CURRENT_TASK:` is reserved for deliberately queued next-turn input and requires explicit `interrupt=false`; `USER_REQUESTED_INTERRUPT:` carries an explicit user stop or replacement request and requires `interrupt=true`. During upgrades, the guard also accepts the former `ORCHESTRATOR_CORRECTION: <reason_code>` form as an immediate compatibility alias, but new prompts do not emit it. An immediate interrupt redirects the current task so the message is handled now; `close_agent` remains a separate operation. Unclassified input, a prefix/`interrupt` mismatch, and explicit non-boolean interrupt values fail closed. An envelope begins on the first non-empty line of the sole text carrier and includes non-empty visible input after its prefix; format, control, separator, or combining characters alone do not count. `message` and `items` cannot be combined, and an `items` payload has one `type: text` item plus any non-text evidence. Non-text items cannot carry a `text` field. Misplaced or repeated delivery literals also fail closed. Its `PostToolUse` matcher covers direct `wait_agent` calls only. When the host surfaces such an event, the guard adds advisory context for `timed_out=true`, empty or missing status, omitted targets, and unrecognized status. A top-level wait result is used directly; when a wrapper includes `structuredContent`, that field is authoritative and the guard never derives status from agent-controlled content text. Nested waits may not produce a direct event, so the Skill and routing reminder remain authoritative. The guard stores no terminal marker and does not register `functions.exec` or `close_agent`; after any accepted input, the Skill requires a later explicit terminal entry before the main agent may close that target. Codex flattens namespaced local function names by concatenation, so the matchers and guard normalize the stable function-name suffix. The guard does not decide whether delegation was appropriate or whether a result is correct.

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
