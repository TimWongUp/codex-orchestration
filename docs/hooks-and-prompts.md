# Hooks and long-lived prompts

## Hooks

This project installs no Hook. Policy Skills, Agent profiles, current tool schemas, and main-agent
acceptance carry its orchestration and Review contracts without a project Hook.

The deterministic procedure in `INSTALL.md` does not inspect `hooks.json` or the Hook directory.
Every Hook registration and file is outside the managed installation projection, including assets
left by earlier project versions. Their removal requires a separate user-directed maintenance plan.
Shared context, memory-routing, closeout, and Codex-native status behavior remain outside this
project's ownership.

## Manager-only prompt branch

Manager-only orchestration is not a Hook or a long-lived setting. It starts only when the user
explicitly asks for it (for example, “enable orchestration mode”, “main agent pure orchestration”,
or “delegate everything to subagents”) and applies only to the current root task. The root Skill
then points to `references/manager-only.md`, where adaptive strong delegation, worker failure
handling, final acceptance, and the explicit user-consent exit are defined. No preference, model
route, CLI flag, configuration file, Agent profile, or global prompt persists the mode. The global
block remains the compact ordinary routing and primary-branch Review pointer shown below.

## Long-lived root-task prompt

`examples/global-agents-block.md` is the canonical compact pair of pointers. Setup injects that exact block
into the active global `AGENTS.override.md` or `AGENTS.md` by default and owns only its markers:

```md
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Agent orchestration

- Root tasks load `codex-orchestration` before creating, coordinating, or waiting for subagents or independent Worktree Roots; simple tasks and ordinary documentation stay with the main agent.

## Code review

- After creating or updating a PR, when asked to review an existing PR including external contributions, or before merging a pull request, branch, or accepted Worktree integration branch into a Git repository's primary branch, load `codex-review-gate`. Review does not depend on CI; reuse valid coverage at merge and supplement affected checks. Ordinary task completion, unmerged handoff without a PR or review request, and repositories without Git history do not trigger it. Its R1-R3 route authorizes only the selected read-only Reviewers; loading the gate classifies the candidate rather than starting a Reviewer, and a current explicit user prohibition still wins. Merge requires separate authorization.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
```

Keep the full workflows in the two policy Skills. The installer preserves all content outside the managed
block, moves the block when Codex's active global file changes, and fails closed on corrupt or
duplicated markers. Repository prompts should not duplicate role lists, task schemas, model routes,
or review rules.
