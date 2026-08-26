# Hooks and long-lived prompts

## Hooks

This project installs no Hook. Policy Skills, Agent profiles, current tool schemas, and main-agent
acceptance carry its orchestration and Review contracts without a project Hook.

The deterministic procedure in `INSTALL.md` does not inspect `hooks.json` or the Hook directory.
Every Hook registration and file is outside the managed installation projection, including assets
left by earlier project versions. Their removal requires a separate user-directed maintenance plan.
Shared context, memory-routing, closeout, and Codex-native status behavior remain outside this
project's ownership.

## Long-lived root-task prompt

`examples/global-agents-block.md` is the canonical compact pair of pointers. Setup injects that exact block
into the active global `AGENTS.override.md` or `AGENTS.md` by default and owns only its markers:

```md
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root tasks load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots; simple tasks and ordinary documentation stay with the main agent.

## Code review

- After repository implementation, tests, dependencies, build or deployment configuration, public contracts, or managed runtime policy change, the root task loads `codex-review-gate` before delivery. Its R1-R3 route authorizes only the selected read-only Reviewers without a separate request; loading the gate classifies the diff rather than starting a Reviewer, and a current explicit user prohibition still wins.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
```

Keep the full workflows in the two policy Skills. The installer preserves all content outside the managed
block, moves the block when Codex's active global file changes, and fails closed on corrupt or
duplicated markers. Repository prompts should not duplicate role lists, task schemas, model routes,
or review rules.
