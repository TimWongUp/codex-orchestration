# Adopt the pure v2 collaboration lifecycle

**Status:** accepted

## Context

The v1 lifecycle mixed creation, input delivery, continuation, interruption, and shutdown into
tools whose return shapes encouraged a target/status map and delivery envelopes. That made it easy
to treat queued input as a new turn, reuse stale terminal evidence, or couple installation to a
guard that could not reliably observe nested calls. The current collaboration API has explicit
tools for each responsibility and the repository must publish one coherent contract.

## Decision

The portable contract is pure v2, and the current model-visible collaboration-tool schemas are the
single source of truth for call mechanics. The repository does not wrap those tools, cache their
descriptions, or define a transport fallback.

The Skill owns only orchestration policy. Ordinary delegation explicitly passes
`fork_turns="none"` with a self-contained task package; bounded transcript context is an explained
exception. A third writable round creates a new agent with a fresh complete package and lease.

After a follow-up is accepted, earlier final notifications and status snapshots for that target are
stale; completion requires a newer final notification reconciled with a fresh snapshot. An explicit
stop freezes new delegation, interrupts every active descendant, and waits for the tree to converge
with no running agent before releasing any active write lease.

The former lifecycle guard and main-agent Route Hook are retired from source, installation
projections, Hook registrations, validation, tests, and active public documentation. At the time of
this decision, `subagent_scope.py` remained as an optional writer-lease Hook. Roles, task packages, the single-writer lease,
coverage/panel/hybrid modes, method Skills, the R0–R3 review gate, and installation safety
boundaries remain unchanged.

The Review ownership and authorization portion of that statement is superseded by
[ADR 0011](0011-separate-delivery-review-from-orchestration.md); lifecycle and installation-safety
claims remain historical context for this decision.

The remaining Hook and rigid task-package portion is superseded by
[ADR 0010](0010-retire-orchestration-hook-and-rigid-briefs.md).

## Consequences

Fresh-context task packages carry the indispensable facts explicitly and keep model routing local
and replaceable. Main-agent waiting is a dependency barrier over mailbox updates, while
`list_agents` and final notifications prevent stale status reuse. Round three requires a new agent
and a new lease, which preserves writer isolation at the cost of not retaining the old thread's
implicit state. Historical ADR 0003 and ADR 0006 remain available for context but no longer define
runtime behavior.
