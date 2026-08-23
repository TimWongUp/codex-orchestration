# Adopt the pure v2 collaboration lifecycle

**Status:** accepted

## Context

The v1 lifecycle mixed creation, input delivery, continuation, interruption, and shutdown into
tools whose return shapes encouraged a target/status map and delivery envelopes. That made it easy
to treat queued input as a new turn, reuse stale terminal evidence, or couple installation to a
guard that could not reliably observe nested calls. The current collaboration API has explicit
tools for each responsibility and the repository must publish one coherent contract.

## Decision

The portable contract is pure v2:

- `spawn_agent` creates an agent. Ordinary delegation explicitly passes `fork_turns="none"` for
  fresh context. A positive value carries bounded partial history and may combine model or
  reasoning-effort overrides. Omitting `fork_turns` or using `"all"` carries full history,
  inherits the parent model and reasoning effort, and rejects those overrides.
- `send_message` queues supplemental information for an existing agent and never starts a turn.
- `followup_task` assigns genuine subsequent or corrective work to an existing non-root agent. A
  running target receives it at the next message boundary or after a pending tool call, while an
  idle target starts its next turn.
- `wait_agent` waits for updates in the caller's mailbox. It is not a target/status map.
- `interrupt_agent` interrupts an active turn while preserving context.
- `list_agents` returns the current agent tree and status snapshot; final notifications are also
  convergence evidence.

There is no v2 close or resume operation. A third writable round creates a new agent with a fresh
complete task package and lease rather than closing an old thread. Supplemental context uses
`send_message`; true later or corrective work uses `followup_task`. Each lifecycle call is a
separate model-visible operation, including when a host exposes it through `functions.exec`.

After a follow-up is accepted, earlier final notifications and status snapshots for that target are
stale; completion requires a newer final notification reconciled with a fresh snapshot. An explicit
stop freezes new delegation, interrupts every active descendant, and waits for the tree to converge
with no running agent before releasing any active write lease.

The former lifecycle guard is retired from source, installation projections, Hook registrations,
validation, tests, and active public documentation. Only `orchestration_route.py` and
`subagent_scope.py` remain as optional Hooks. Roles, task packages, the single-writer lease,
coverage/panel/hybrid modes, method Skills, the R0–R3 review gate, and installation safety
boundaries remain unchanged.

## Consequences

Fresh-context task packages carry the indispensable facts explicitly and keep model routing local
and replaceable. Main-agent waiting is a dependency barrier over mailbox updates, while
`list_agents` and final notifications prevent stale status reuse. Round three requires a new agent
and a new lease, which preserves writer isolation at the cost of not retaining the old thread's
implicit state. Historical ADR 0003 and ADR 0006 remain available for context but no longer define
runtime behavior.
