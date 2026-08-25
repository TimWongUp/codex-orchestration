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

- Root task only: load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots.
- Each root task owns local Git, local acceptance, and validation; while lanes are nonterminal, neither the Integration Root nor its local workers write the repository; afterward it owns handoff acceptance, merges, final review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Official Worktree Roots require the user's explicit request and the Skill's admission gate; one Integration Root coordinates at most three nonterminal lanes.
- Each root task has one active writer selected by that root; writable workers receive a bounded natural-language brief, and derived agents never call collaboration tools or orchestrate other agents.

## Code review

- When repository implementation, tests, dependencies, build or deployment configuration, public contracts, or managed runtime policy changed, the root task loads `codex-review-gate` before final delivery and applies its R0-R3 route to the final integrated diff.
- R0 has no independent Reviewer; R1-R3 use the read-only Reviewers selected by the gate. This rule authorizes only those Reviewer calls without a separate current-turn user request, unless the current user explicitly prohibits subagents or Reviewers.
- Main-agent diff inspection and validation are not independent Review. The main agent remediates accepted findings; R3 completes with an `adversarial-verifier` after remediation and validation.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
```

Keep the full workflows in the two policy Skills. The installer preserves all content outside the managed
block, moves the block when Codex's active global file changes, and fails closed on corrupt or
duplicated markers. Repository prompts should not duplicate role lists, task schemas, model routes,
or review rules.
