# Hooks and long-lived prompts

## Optional hooks

`subagent_scope.py` injects one high-priority check only for writable worker roles: a complete
canonical lease package must be present before writing. Read-only agents receive no extra Hook
context because their identity, scope, and panel boundaries already live in Agent profiles.

The Hook is optional during the deterministic procedure in `INSTALL.md`. Setup copies the script,
shows the exact `hooks.json` merge, writes the platform-appropriate command fields, and preserves
unrelated Hook groups. Runtime validation checks it only when explicitly invoked with `--hooks`.
Hook text never grants a write lease. Codex treats it as a non-managed Hook, so the user reviews
and trusts its current hash with `/hooks` after installation.

The former project `UserPromptSubmit` route Hook is retired because the Skill, repository prompt,
and current tool schemas already carry the main-agent policy. A machine may register shared
context, memory-routing, or closeout Hooks from another repository alongside this Hook. Those
registrations and Codex-native agent status notifications remain outside this project's ownership.

## Long-lived main-agent prompt

`examples/global-agents-block.md` is the canonical compact pointer. Setup injects that exact block
into the active global `AGENTS.override.md` or `AGENTS.md` by default and owns only its markers:

```md
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Subagent orchestration

- Main agent only: load `codex-orchestration` before creating, coordinating, or waiting for subagents, and apply its Review risk gate before delivery when code changed.
- The main agent owns Git, acceptance, review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Writable workers require the canonical single-writer lease; derived agents never orchestrate descendants.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
```

Keep the full workflow in the Skill. The installer preserves all content outside the managed
block, moves the block when Codex's active global file changes, and fails closed on corrupt or
duplicated markers. Repository prompts should not duplicate role lists, task schemas, model routes,
or review rules.
