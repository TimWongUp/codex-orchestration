<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root tasks load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots; simple tasks and ordinary documentation stay with the main agent.

## Code review

- After repository implementation, tests, dependencies, build or deployment configuration, public contracts, or managed runtime policy change, the root task loads `codex-review-gate` before delivery. Its R1-R3 route authorizes only the selected read-only Reviewers without a separate request; loading the gate classifies the diff rather than starting a Reviewer, and a current explicit user prohibition still wins.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
