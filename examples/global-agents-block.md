<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root tasks load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots; simple tasks and ordinary documentation stay with the main agent.

## Code review

- After creating or updating a PR, when asked to review an existing PR including external contributions, or before merging a pull request, branch, or accepted Worktree integration branch into a Git repository's primary branch, load `codex-review-gate`. Review does not depend on CI; reuse valid coverage at merge and supplement affected checks. Ordinary task completion, unmerged handoff without a PR or review request, and repositories without Git history do not trigger it. Its R1-R3 route authorizes only the selected read-only Reviewers; loading the gate classifies the candidate rather than starting a Reviewer, and a current explicit user prohibition still wins. Merge requires separate authorization.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
