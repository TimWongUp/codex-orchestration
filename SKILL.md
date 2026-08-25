---
name: codex-orchestration
description: Orchestrate Codex custom subagents and independent Worktree Roots for explicit delegation, parallel investigation or implementation, writable worker leases, and model-diverse panels. Use when the user asks for subagents, parallel work, or official Codex worktrees, when codex-review-gate selects R1-R3 Reviewers, or when a coding task has a clear delegation payoff. Keep simple tasks and ordinary documentation with the main agent. Derived subagents must not invoke this Skill.
metadata:
  version: 0.9.1
---

# Codex subagent orchestration

## Authority

This Skill belongs to root Codex tasks. A Worktree Root is an independent task and session, not a
derived agent, so it has the same local orchestration authority as any other root inside its lane.
Derived agents do not call collaboration tools or create, coordinate, wait for, interrupt, message,
manage, or summarize any other agent. Do not load or execute this Skill from a derived agent;
panel membership never grants orchestration authority.

The main agent owns the goal, decomposition, model selection, local write lease, Git, acceptance,
and delivery. An Integration Root additionally owns peer-lane coordination and integrated
acceptance. Delegate only when the result can change a decision or materially improve execution.
`codex-review-gate` separately authorizes only the read-only Reviewers selected for R1-R3; that
permission does not admit unrelated implementation or investigation delegation.

## Route the work

Keep simple tasks and ordinary documentation with the main agent. Route repository exploration to
`explorer`, official contracts or version facts to `reference-researcher`, and public practice or
product evidence to `web-researcher`. Use public research only when it can change the decision and
local or official sources do not already answer it.

The main agent directly reads project-owned architecture, ADR, and handoff documents that define
the decision frame. The active writer reads the exact code it changes. For delegated reading,
verify decision-critical or suspicious claims from returned paths, symbols, quotations, or focused
samples. Claims that something is absent identify the searched boundary and terms.

Before creating two or more read-only agents, read
[references/read-only-collaboration.md](references/read-only-collaboration.md) and choose its
`coverage`, `panel`, or `hybrid` mode.

Before selecting a model for any delegation, read
[references/model-routing.md](references/model-routing.md). Ordinary delegation sets
`fork_turns="none"` and sends a self-contained brief. Bounded transcript context is an explained
exception. Current collaboration-tool schemas are the sole authority for supported parameters and
resolved-model evidence.

## Single writer

One root task has one active writer: the main agent or one worker with an explicit lease. The lease
is local to that task and checkout; independent Worktree Roots do not share one cross-session
lease.

Before creating a writable worker, read
[references/worker-writing.md](references/worker-writing.md) and apply its admission, brief,
round, and acceptance contract. While the lease is active, the main agent and all other agents are
read-only. The worker never performs Git operations or external writes. No prior lease is extended
into another round.

## Independent Worktree Roots

Do not create a worktree unless the user explicitly requests one. When two or three isolated
writable lanes may qualify, read [references/worktree-roots.md](references/worktree-roots.md)
before creating or coordinating official Worktree Roots. Use current task/thread tools, not a
derived-agent spawn. The reference owns admission, at-most-three lane coordination, repository
read-only integration, handoff, batch acceptance, integration, and stop convergence.

## Task language and brief

Follow an explicit user language request. Otherwise read
`$CODEX_HOME/codex-orchestration/preferences.toml` when it exists and use its supported
`task_package_language` value (`en` or `zh-CN`); without it, match the current user's language.
Keep role names, paths, and tool or protocol literals unchanged.

Give each agent one primary outcome in a compact natural-language brief. Include only context the
agent cannot cheaply recover, the handoff focus, and useful files, diffs, logs, or URLs. State
exclusions, authority boundaries, validation expectations, or completion signals only when they
materially change the assignment. Ask for decision-relevant evidence rather than fixed field
labels; redact sensitive data and omit unrelated conversation history and reasoning.

## Lifecycle

Pending agent work is a dependency barrier: wait before any decision, write, or final answer it
could change, while continuing independent work outside the delegated scope. Reconcile accepted
results with the current repository or evidence before acting.

Before sending a same-thread follow-up, interrupting or replacing an agent, responding to slow or
sparse progress, or stopping agent work, read
[references/collaboration-lifecycle.md](references/collaboration-lifecycle.md). It owns stale-result
handling after follow-ups, interruption/replacement choices, and stop convergence; ordinary waits
use the inline dependency barrier. Worktree-batch lifecycle also follows
[references/worktree-roots.md](references/worktree-roots.md).

A branch receives at most three writable worker rounds: initial implementation; one same-thread
correction after the target is idle; then, only when requested by acceptance or Review, one new
worker selected through [references/model-routing.md](references/model-routing.md). After round
three, the main agent takes over, decomposes again, or reports the blocker.

## Git and review handoff

The main agent owns branch creation, commits, merges, pushes, and pull requests. A Worktree Root
owns Git only inside its lane and returns one candidate handoff branch; its Integration Root owns
cross-lane integration and publishing. Workers do not use Git.

`codex-review-gate` defines the review route and authorizes its R1-R3 read-only Reviewers. The root
main agent classifies the final integrated diff, selects roles, remediates accepted findings,
verifies the result, and decides delivery. For selected Reviewers, use this Skill's model routing,
brief, lifecycle, and waiting rules without reapplying the proactive-delegation threshold.

## Runtime boundary

Role, lease, and task contracts are not operating-system access controls. Accept worker results
only after inspecting the complete diff, scope, and validation evidence.

Keep the main agent as writer when inputs may contain unisolated prompt injection or the complete
resulting diff cannot be inspected reliably.
