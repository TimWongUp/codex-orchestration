---
name: codex-review-gate
description: Apply the independent R0-R3 delivery review gate after repository implementation, tests, dependencies, build or deployment configuration, public contracts, or managed runtime policy changes and before final delivery. Use whenever an applicable project, user, or workflow rule requires risk-based review, including final integrated diffs from staged work or Worktree Roots. This Skill defines the risk route and authorizes its read-only Reviewers; the root main agent executes classification, remediation, verification, and delivery. It does not authorize implementation delegation or Worktree creation.
metadata:
  version: 0.10.2
---

# Codex delivery review gate

## Authority

This Skill defines a delivery control, not an admission test for ordinary implementation or
investigation delegation. Apply it from the root task after the final diff is available and before
delivery. A project, user, or workflow instruction requiring this gate already authorizes the
read-only reviewers selected by R1-R3; the current user message does not need to name a subagent or
Reviewer again. A current explicit user prohibition on subagents or Reviewers still takes priority.

The main agent owns the classification, final diff inspection, validation, remediation, Git, and
delivery. Reviewers remain read-only. Load `codex-orchestration` only when R1-R3 needs Agent
execution, then use its model routing, brief, lifecycle, and waiting contracts. R0 needs no Agent
solely for review.

## Classify the final diff

Choose the highest matching level. Changed line or file counts never determine a level by
themselves. When evidence does not distinguish two adjacent levels, choose the higher one.

| Level | Highest matching condition | Independent review |
| --- | --- | --- |
| R0 | The change does not alter runtime behavior and is mechanical, local, and completely verifiable. It does not change dependencies, build or deployment behavior, public contracts, test semantics, or security policy. | None; the main agent inspects the complete diff and validates it. |
| R1 | The change is not R0, remains localized, has one material risk dimension, is covered by relevant validation, and is easy to detect and recover if wrong. This includes localized runtime, public-contract, managed-policy, test-semantic, dependency, or build changes. | One Reviewer; select its role by the R1 rule below. |
| R2 | The change has two or more independent material risk dimensions, changes a broad or hard-to-recover public contract, or touches a sensitive boundary such as security, privacy, concurrency, data compatibility, or deployment. | At least one matching Reviewer; add seats only for additional material hypotheses that need independent judgment, never to fill a quota. |
| R3 | The change defines or weakens a trust or authorization boundary, or failure could cause unauthorized access, code execution, secret exposure, irreversible data loss, financial impact, supply-chain compromise, or a broad production outage. Also use R3 when earlier review reveals a material flaw that changes the original risk assumptions. | At least one focused Reviewer, main-agent remediation, then an `adversarial-verifier`. |

If a change does not fully match R0, R1, or R3 and no explicit R2 condition applies, classify it as
R2. This fail-closed fallback covers missing validation, uncertain recoverability, and unusual
non-runtime changes without expanding the table.

Risk dimensions include correctness and regressions, architecture and public contracts, security
and privacy, concurrency and state, data compatibility and migrations, test reliability,
performance and resources, and deployment or supply-chain impact. Count distinct failure
hypotheses, not role names. Risk level expresses impact; Reviewer count follows only the distinct
material hypotheses for which independent judgment can change delivery. R1-R3 always select at
least one matching Reviewer; additional seats require additional hypotheses. A validation-proven
property, missing evidence axis, or desired headcount does not create an extra seat. Assign every
Reviewer a different material risk and evidence boundary.

For R1, `correctness-reviewer` is the general default. When the sole material hypothesis is
specifically architectural, security-related, performance-related, test-related, or otherwise
specialist, select the matching Reviewer instead. The specialist replaces the default; it does not
create a second seat for the same hypothesis.

## Execute the gate

1. Pin the comparison boundary and confirm the final diff is non-empty. Inspect that diff, affected
   contracts, validation evidence, and recoverability. Select R0-R3 and retain one concise reason
   naming the highest matching condition.
2. For R0, finish main-agent validation. For R1-R3, load `codex-orchestration`, select the matching
   read-only roles, give each Reviewer a concrete failure hypothesis and evidence boundary, and wait
   for every result that can affect delivery.
3. Treat Reviewer output as a hypothesis. Reconcile every finding against the actual diff and its
   cited evidence. The main agent fixes accepted findings or records evidence for rejecting them,
   then reruns affected validation. Do not repeat Review merely to obtain a clean report.
4. For R3, run `adversarial-verifier` only after focused review, remediation, and validation are
   complete, or after focused review and validation when no fix was required. Give it the final diff,
   original high-impact hypothesis, earlier findings, remediation, and validation evidence. Treat an
   overturned conclusion as a new finding and repeat remediation and verification.
5. Deliver only after the selected gate is complete. State the level, the decisive reason, the
   Reviewer coverage, and any residual risk in the final handoff.

## Integrated and staged changes

Classify one final integrated diff after accepted stages or Worktree Root branches are merged and
combined validation has run. Lane or intermediate review does not replace this gate. Add an
intermediate review only when unreviewed risk would otherwise compound before integration.
