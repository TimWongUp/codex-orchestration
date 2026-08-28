<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root tasks load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots; simple tasks and ordinary documentation stay with the main agent.

## Code review

- Before merging a pull request, branch, or accepted Worktree integration branch into a Git repository's primary branch, the merge-owning root loads `codex-review-gate` after validation and against the latest candidate diff. Ordinary task completion, unmerged handoff, pull-request creation or update without an imminent merge, and repositories without Git history do not trigger it. Its R1-R3 route authorizes only the selected read-only Reviewers without a separate request; loading the gate classifies the candidate rather than starting a Reviewer, and a current explicit user prohibition still wins.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
