# Separate delivery review from agent orchestration

**Status:** accepted

**Supersedes:** the Review ownership and authorization clauses in ADR 0007, and the single-policy-
Skill global-pointer wording in ADR 0008.

## External reference points

No reviewed source defines this suite's R0-R3 taxonomy; the mapping is local. Its shape follows
four established practices: Google's review guidance treats line count as an imperfect size proxy
and calls for qualified coverage of specialist areas such as security, privacy, and concurrency;
GitLab approval rules can require different reviewer categories and multiple independent rules;
NIST SSDF PW.7 requires code review or analysis plus triage and remediation; and OWASP recommends
risk-based scheduling that distinguishes routine diffs from high-risk components.

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Google Engineering Practices: What to look for](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [GitLab: Merge request approval rules](https://docs.gitlab.com/user/project/merge_requests/approvals/rules/)
- [NIST SP 800-218: Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
- [OWASP Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html)

## Decision

Optional delegation and mandatory delivery Review had different triggers and authority but shared
one Skill, so a restriction on proactive subagents could incorrectly suppress the R0-R3 gate. The
suite now gives `codex-review-gate` authority to define the risk route and authorize only its R1-R3
read-only Reviewers, while the root main agent executes classification, role selection,
remediation, verification, and delivery. `codex-orchestration` retains Agent execution, model
routing, lifecycle, writer leases, and Worktree coordination. An applicable Review rule authorizes
those Reviewer calls without a repeated current-turn request, unless the current user explicitly
prohibits them; it does not authorize implementation delegation. The managed global rules expose
orchestration and code Review as separate pointers, and deterministic installation projects both
Skills. They remain components of one released suite and share its version; the separation is an
authority boundary, not an independent distribution channel.

Risk level expresses impact and recoverability, not a Reviewer quota. R1-R3 always select at least
one matching Reviewer; extra seats follow only additional material failure hypotheses for which
independent judgment can change delivery. Passing mechanical validation, an absent evidence axis,
or a desired headcount does not create an extra seat. Reviewer findings remain hypotheses until the
root main agent verifies their cited evidence against the pinned final diff, and Review is not
repeated solely to obtain a clean report.
