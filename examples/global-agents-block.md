<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root task only: load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots, and apply its Review risk gate before final delivery when code changed.
- Each root task owns local Git, local acceptance, and validation; while lanes are nonterminal, neither the Integration Root nor its local workers write the repository; afterward it owns handoff acceptance, merges, final review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Official Worktree Roots require the user's explicit request and the Skill's admission gate; one Integration Root coordinates at most three nonterminal lanes.
- Each root task has one active writer selected by that root; writable workers receive a bounded natural-language brief, and derived agents never orchestrate descendants.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
