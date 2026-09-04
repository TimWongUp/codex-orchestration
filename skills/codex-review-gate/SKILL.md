---
name: codex-review-gate
description: Apply the R0-R3 pre-merge Review gate when a Git-managed repository is about to merge a pull request, branch, or accepted Worktree integration branch into its primary branch. It selects and authorizes read-only Reviewers for R1-R3; the root handles classification, remediation, validation, and integration. Do not use it for ordinary task completion, unmerged handoffs, or repositories without Git history.
metadata:
  version: 0.10.7
---

# Codex pre-merge review gate

## Authority

This Skill is a primary-branch integration control, not a task-completion or ordinary-delegation
control. Apply it only from the root task that is about to merge a pull request, branch, or accepted
Worktree integration branch into the repository's primary branch. Opening or updating a pull
request, pushing or handing off a branch, finishing implementation, and delivering an unmerged
candidate do not trigger the gate. A future task that owns the merge owns the Review.

First determine whether the gate applies:

1. The project is a Git repository with committed source and primary-branch histories.
2. The current workflow includes an imminent merge into the primary branch.

When either condition is absent, stop before R0-R3 classification and continue normal main-agent
validation and handoff. Repositories without Git history never use this gate. When both conditions
hold, the root must pin the latest candidate diff from the target merge base to the candidate head.
If the merge is imminent but the root cannot pin that diff, fetch the required history or resolve
the ambiguous refs; the candidate must not merge until the boundary is pinned. A project, user, or
workflow rule requiring a pre-merge Review authorizes its selected R1-R3 read-only Reviewers without
a separate current-turn request; a current explicit user prohibition on subagents or Reviewers still
wins.

The merge-owning root owns classification, candidate diff inspection, finding decisions,
remediation authority, validation, Git, and integration. In ordinary mode, the main agent may
implement an accepted fix. In manager-only mode, the leased worker implements the accepted fix and
runs affected validation; the root inspects and accepts that result before the original Reviewer
performs its targeted follow-up. The R3 route's main-agent remediation label names this root
authority and coordination; it does not require the root to edit code.
R0 needs no Agent solely for Review; for R1-R3, load `codex-orchestration` and use its model routing,
brief, lifecycle, and waiting contracts.

## Classify the candidate diff

Choose the highest matching level. Changed line or file counts never determine a level by
themselves. When evidence does not distinguish two adjacent levels that both plausibly match,
choose the higher one.

| Level | Highest matching condition | Independent review |
| --- | --- | --- |
| R0 | The change is local and self-contained, completely verifiable by the main agent at the boundary where its behavior is observable, easy to detect and recover if wrong, and leaves no material failure hypothesis that current validation does not exclude and independent judgment could change. It does not change dependencies, build or deployment behavior, public contracts, test semantics, or security policy. Runtime behavior changes may qualify; a self-contained illustrative or demonstration artifact with no network, auth, persistence, secret, dependency, or contract surface, verified at its target boundaries, is a typical example. | None; the main agent inspects the complete diff and validates it. |
| R1 | The change is not R0, remains localized, is covered by relevant validation, is easy to detect and recover if wrong, and has exactly one material failure hypothesis that current validation does not exclude and independent judgment could change. A localized runtime, public-contract, managed-policy, test-semantic, dependency, or build change qualifies only when that hypothesis exists; without one, complete the missing validation — classify the change as R0 only when every R0 condition and exclusion is satisfied, and otherwise apply the R2 fallback. | One Reviewer; select its role by the R1 rule below. |
| R2 | The change has two or more independent material risk dimensions, changes a broad or hard-to-recover public contract, or touches a sensitive boundary such as security, privacy, concurrency, data compatibility, or deployment. | At least one matching Reviewer; add seats only for additional material hypotheses that need independent judgment, never to fill a quota. |
| R3 | The change defines or weakens a trust or authorization boundary, or failure could cause unauthorized access, code execution, secret exposure, irreversible data loss, financial impact, supply-chain compromise, or a broad production outage. Also use R3 when earlier review reveals a material flaw that changes the original risk assumptions. | At least one focused Reviewer, main-agent remediation, then an `adversarial-verifier`. |

If a change does not fully match R0, R1, or R3 and no explicit R2 condition applies, classify it as
R2. This fail-closed fallback covers material uncertainty such as missing validation, uncertain
recoverability, or an unclear risk boundary; the mere presence of runtime behavior is not
uncertainty, and a verified, recoverable change with no material failure hypothesis belongs in R0.

Risk dimensions include correctness, architecture, public contracts, security, privacy,
concurrency, state, data compatibility, migrations, test reliability, performance, resources,
deployment, and supply-chain impact. Count failure hypotheses, not role names. R1-R3 always select
at least one matching Reviewer; add a seat only for another material hypothesis where independent
judgment can change integration. Proven properties, missing evidence axes, and desired headcount
add no seat. Give every Reviewer a distinct material risk and evidence boundary.

For R1, `correctness-reviewer` is the general default. When the sole material hypothesis is
specifically architectural, security-related, performance-related, test-related, or otherwise
specialist, select the matching Reviewer instead. The specialist replaces the default; it does not
create a second seat for the same hypothesis.

## Execute the gate

1. After implementation and relevant validation are complete, pin the primary branch, merge base,
   and latest candidate head; confirm the pre-merge diff is non-empty. Inspect that diff, affected
   contracts, validation evidence, and recoverability. Select R0-R3 and retain one concise reason
   naming the highest matching condition; an R0 reason must state the completed validation and why
   no material failure hypothesis remains.
2. For R0, finish main-agent validation. For R1-R3, load `codex-orchestration`, select the matching
   read-only roles, give each Reviewer a concrete failure hypothesis and evidence boundary, and wait
   for every result that can affect the merge.
3. Treat Reviewer output as a hypothesis. The merge-owning root reconciles every finding against
   the actual diff and its cited evidence, decides whether to accept it, and retains remediation
   and validation authority. In ordinary mode, the main agent may fix an accepted finding. In
   manager-only mode, assign the accepted fix to the leased worker, which implements it and reruns
   affected validation; the root then inspects and accepts the result. After the root accepts the
   fix, send the original Reviewer a same-thread targeted follow-up to verify that finding against
   the candidate diff. This resolves the assigned finding; it is not a new full Review. Do not
   repeat full Review merely to obtain a clean report.
4. For R3, run `adversarial-verifier` only after focused review, remediation, and validation are
   complete, or after focused review and validation when no fix was required. Give it the candidate
   diff, original high-impact hypothesis, earlier findings, remediation, and validation evidence.
   Treat an overturned conclusion as a new finding and repeat remediation and verification.
5. Merge only after the selected gate is complete. State the level, decisive reason, Reviewer
   coverage, and any residual risk in the merge handoff. If new substantive changes land after the
   reviewed candidate, re-pin and reclassify the changed candidate; an accepted-finding fix still
   uses the targeted follow-up above rather than a new full Review.

## Integrated and staged changes

Classify one final integrated candidate diff after accepted stages or Worktree Root branches are
merged into an integration branch, combined validation has run, and that branch is about to merge
into the primary branch. If the current task only hands off the integration branch, defer the gate
to the future merge-owning task. Lane or intermediate review does not replace this gate. Add an
optional early design or focused consultation only when its result can prevent risk from
compounding; it is not the pre-merge gate.
