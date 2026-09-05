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

Start risk Review after creating or updating a PR and when asked to review an existing PR,
including external contributions. The final primary-branch integration boundary remains a check
that valid Review and required validation cover the latest candidate, not a requirement to start
another full Review. PR work includes automatic Review; merging remains separately authorized.

CI availability does not determine whether Review starts. Run Review alongside relevant CI where
configured, and use appropriate local validation otherwise. A blocked or missing expected CI run
is not a pass. Review authority does not grant permission to edit contributor branches or execute
untrusted workflow changes with credentials. These instructions do not install event automation.

Git history and a pinned candidate remain required evidence: the merge remains blocked until the required history and refs are available.
When head or target/base changes, inspect changed behavior and integration effects, retain valid
coverage, and supplement affected risks. Repeat a full Review only when earlier conclusions cannot
be preserved. Fixes for accepted findings retain same-thread targeted follow-up.

## Consequences

PR feedback can arrive while CI runs without weakening the final merge requirement. Ordinary local
completion and branch-only handoffs still use normal validation. The review-owning root records
enough candidate and risk evidence for the merge-owning root to reuse it; approval text alone is
insufficient. Integrated candidates require combined-risk coverage, not mechanically duplicated
lane reviews. R0-R3 thresholds and Reviewer selection remain unchanged.
