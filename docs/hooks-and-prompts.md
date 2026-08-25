# Hooks and long-lived prompts

## Hooks

This project installs no Hook. The former `subagent_guard.py`, `subagent_scope.py`, and
`orchestration_route.py` Hooks duplicated policy already carried by the Skill, Agent profiles,
current tool schemas, and main-agent acceptance. Their prompt injection also made natural task
briefs look like fixed authorization forms without creating an operating-system security boundary.

The deterministic procedure in `INSTALL.md` retires only copies and registrations whose prior
project ownership can be authenticated. It preserves unrelated Hook groups. Shared context,
memory-routing, closeout, and Codex-native status behavior remain outside this project's ownership.

## Long-lived root-task prompt

`examples/global-agents-block.md` is the canonical compact pointer. Setup injects that exact block
into the active global `AGENTS.override.md` or `AGENTS.md` by default and owns only its markers:

```md
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root task only: load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots, and apply its Review risk gate before final delivery when code changed.
- Each root task owns local Git, local acceptance, and validation; while lanes are nonterminal, neither the Integration Root nor its local workers write the repository; afterward it owns handoff acceptance, merges, final review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Official Worktree Roots require the user's explicit request and the Skill's admission gate; one Integration Root coordinates at most three nonterminal lanes.
- Each root task has one active writer selected by that root; writable workers receive a bounded natural-language brief, and derived agents never orchestrate descendants.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
```

Keep the full workflow in the Skill. The installer preserves all content outside the managed
block, moves the block when Codex's active global file changes, and fails closed on corrupt or
duplicated markers. Repository prompts should not duplicate role lists, task schemas, model routes,
or review rules.
