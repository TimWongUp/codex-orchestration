# Route review by material failure hypothesis

**Status:** accepted

**Refines:** [ADR 0011](0011-separate-delivery-review-from-orchestration.md). Its authority split,
Reviewer authorization, remediation loop, and "risk level expresses impact and recoverability"
philosophy remain in force; this decision extends that philosophy to the R0/R1 boundary.

## External reference points

The references behind ADR 0011 also support a risk-hypothesis boundary: NIST SSDF PW.7 requires
review or analysis with triage and remediation but does not require a second reviewer for every
diff, and Google's review guidance asks reviewers to focus on what materially matters rather than
size proxies.

- [NIST SP 800-218: Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
- [Google Engineering Practices: What to look for](https://google.github.io/eng-practices/review/reviewer/looking-for.html)

## Decision

R0 previously required that a change "does not alter runtime behavior". Combined with R1's
inclusion of localized runtime changes and the fail-closed R2 fallback, any change that introduced
or altered runtime behavior — including a self-contained illustrative HTML page the main agent had
already verified — necessarily selected at least one independent Reviewer. The only exits were
non-behavioral changes or an explicit user prohibition.

The R0/R1 boundary is now the material failure hypothesis. R0 admits local, self-contained changes
that the main agent completely verified at the boundary where their behavior is observable, that
are easy to detect and recover, that avoid dependencies, build or deployment behavior, public
contracts, test semantics, and security policy, and that leave no material failure hypothesis
current validation does not exclude and independent judgment could change. Runtime behavior
changes may qualify. Self-contained illustrative or demonstration artifacts with no network, auth,
persistence, secret, dependency, or contract surface are named as R0 examples, not as an exemption
category. R1 requires exactly one such hypothesis; a localized runtime, public-contract,
managed-policy, test-semantic, dependency, or build change qualifies only when it exists. The R2
fallback covers material uncertainty — missing validation, uncertain recoverability, or an unclear
risk boundary — not the mere presence of runtime behavior. An R0 delivery reason must state the
completed validation and why no material failure hypothesis remains.

The gate-loading trigger, the delegation-threshold decoupling from ADR 0011, "R1-R3 always select
at least one matching Reviewer", the same-thread remediation follow-up, and R3 adversarial
verification are unchanged.

## Consequences

Verified, recoverable, low-impact behavior changes no longer force a Reviewer, and agents can no
longer route every localized runtime change to R1 by default. The residual risks are under-review
and R0 becoming an escape hatch; they are contained by the hard exclusions inside R0, the required
concrete R0 reason, and the retained fail-closed fallback for material uncertainty. Product-type
exemptions are deliberately rejected: "demo" or "illustrative" labels are supporting evidence, not
a classification. `scripts/validate.py`, both README files, `docs/architecture.md`,
`docs/configuration.md`, `docs/hooks-and-prompts.md`, and `examples/global-agents-block.md` stay
synchronized with this boundary.
