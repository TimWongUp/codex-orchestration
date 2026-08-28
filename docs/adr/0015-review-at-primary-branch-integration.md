# Review at the primary-branch integration boundary

**Status:** accepted

**Refines:** [ADR 0009](0009-coordinate-independent-worktree-roots.md),
[ADR 0011](0011-separate-delivery-review-from-orchestration.md), and
[ADR 0014](0014-risk-hypothesis-gate-threshold.md). Their Worktree ownership, authority split,
R0-R3 taxonomy, Reviewer selection, remediation loop, and risk-hypothesis threshold remain in
force; this decision replaces their task-delivery and unconditional integrated-review triggers.

## External reference points

GitHub branch protection, GitLab merge-request approvals, and Azure Repos all place required Review
at the merge boundary. GitHub can require approval of the most recent reviewable push; GitLab
cancels auto-merge when new commits arrive; Azure describes Review as examination of proposed
changes before they enter the target branch. Google's process likewise reviews a change list before
submission while allowing earlier feedback on major design problems.

- [GitHub: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitLab: Merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
- [GitLab: Auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)
- [Azure Repos: Review pull requests](https://learn.microsoft.com/en-us/azure/devops/repos/git/review-pull-requests)
- [Google Engineering Practices: Navigating a CL in review](https://google.github.io/eng-practices/review/reviewer/navigate.html)

## Decision

The mandatory `codex-review-gate` is a primary-branch integration control. It runs once against the
latest validated candidate when the current root task is about to merge a pull request, branch, or
accepted Worktree integration branch into the repository's primary branch. Opening or updating a
pull request, finishing implementation, pushing or handing off an unmerged branch, and delivering a
candidate do not trigger the gate; the future task that owns the merge owns the Review.

Git history and an imminent primary-branch merge determine whether the gate applies. Without either,
normal main-agent validation still applies but R0-R3 classification and independent Review do not.
Once an imminent merge exists, a pinned merge-base-to-candidate diff is required evidence: if the
root cannot pin it, the merge remains blocked until the required history and refs are available.
Optional early architecture, security, or specialist consultation remains available when it can
prevent risk from compounding, but it is not the mandatory pre-merge gate.

## Consequences

Review no longer delays ordinary task delivery or duplicates validation for repositories and
artifacts that have no integration boundary. Worktree lanes and unmerged integration branches can
be handed off without Review; the merge-owning root reviews the final combined candidate once.
New substantive changes after Review stale the candidate and require reclassification, while fixes
for accepted findings retain the same-thread targeted follow-up. Direct work already on the primary
branch has no eligible merge boundary and is not retroactively made compliant by this gate; normal
repository workflow should keep mergeable work on a candidate branch.
