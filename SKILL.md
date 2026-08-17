---
name: codex-orchestration
description: Orchestrate Codex custom subagents for explicit delegation, parallel investigation, writable worker leases, model-diverse panels, and risk-based review. Use when the user asks for subagents or parallel work, or when a coding task has a clear delegation payoff. Keep simple tasks and ordinary documentation with the main agent. Derived subagents must not invoke this Skill.
metadata:
  version: 0.2.0
---

# Codex subagent orchestration

## Authority

This Skill belongs to the main agent. Derived agents do not create, coordinate, wait for, or summarize other agents.

The main agent owns the goal, decomposition, model selection, write lease, Git operations, acceptance, review, and final delivery. Delegate only when the result is likely to change the decision or materially improve execution.

## Roles

- `worker`: bounded production implementation.
- `diagnosing-bugs-worker`: difficult bugs or performance regressions with an unknown cause; load and follow the `diagnosing-bugs` Skill.
- `prototype-worker`: throwaway code that answers one design question; load and follow the `prototype` Skill.
- `explorer`: local entry points, call paths, data flow, and tests.
- `reference-researcher`: official documentation, standards, papers, and version facts.
- `web-researcher`: ecosystem practice, product patterns, case studies, postmortems, and community experience.
- `frontend-design`: visual, interaction, and accessibility direction.
- `default`: a single read-only workstream without a dedicated role.
- `correctness-reviewer`, `architecture-reviewer`, `security-reviewer`, `performance-reviewer`, `test-reliability-reviewer`: focused review roles.
- `specialist-reviewer`: one low-frequency specialty named in `SPECIALTY`.
- `adversarial-verifier`: attempts to overturn an accepted conclusion after high-risk remediation.
- `expert`: executes one explicitly supplied expert perspective.

## Research routing

- Current repository evidence goes to `explorer`.
- Official contracts and version facts go to `reference-researcher`.
- Public implementation practice and product patterns go to `web-researcher`.

For feature, product, architecture, or technology choices, create `web-researcher` only when public evidence can change the decision and local or official sources do not already answer the question. Use `coverage` when multiple evidence classes are independently necessary.

## Read-only collaboration modes

Choose a mode before creating two or more read-only agents:

- `coverage`: separate evidence ranges or risk hypotheses.
- `panel`: normally two or three different models answer the same task independently.
- `hybrid`: one same-task panel plus separate specialist workstreams.

Add this line to every multi-agent read-only task package:

```text
EVALUATION MODE: coverage | panel | hybrid
```

Panel members receive the same GOAL, SCOPE, CONSTRAINTS, DONE WHEN, RETURN, and source material. Change only the model. Synthesize consensus, material disagreement, and evidence quality; do not use a majority vote as the decision rule.

## Model routing

Read [references/model-routing.md](references/model-routing.md) before spawning an agent. Follow the user's local routing file when present; otherwise inherit the current Codex defaults. Agent TOML files never pin models.

## Single writer

One root task has one active writer: either the main agent or one worker with an explicit lease.

Before creating a writable worker, read [references/worker-writing.md](references/worker-writing.md). While the lease is active, the main agent and every other agent remain read-only. The worker never performs Git operations or external writes.

## Read-only task package

```text
GOAL: one primary outcome
SCOPE: necessary context and investigation boundary
CONSTRAINTS: contracts whose violation means failure
DONE WHEN: observable completion condition
RETURN: result format, evidence, uncertainty, and impact
```

Reviewers append:

```text
RISK: the concrete failure hypothesis
EVIDENCE: the diff, files, sources, and evidence boundary
```

`specialist-reviewer` also requires one `SPECIALTY`.

Each delegation has one primary outcome. Agents may complete unavoidable direct dependencies, but they do not add adjacent refactors, features, or workstreams.

## Worker rounds

A branch receives at most three writable worker rounds:

1. Initial implementation.
2. The same thread and model address explicit acceptance or review findings.
3. Only when the main agent or reviewer requests another write round; start a new worker with the next available model route.

After round three, the main agent takes over, decomposes again, or reports the blocker. The final pull-request review has no round limit because reviewers are read-only and the main agent controls remediation.

## Git and staged work

- The main agent owns branch creation, commits, merges, pushes, and pull requests.
- Ordinary work uses one short-lived task branch.
- Multi-stage work uses one integration branch and serial stage branches created from the latest accepted state.
- Prototype branches remain separate until the user accepts the direction. Delete them only after that confirmation.
- Do not create a worktree unless the user explicitly requests one.

## Review gate

- R0: no independent reviewer.
- R1: one reviewer for the most material risk.
- R2: multiple non-overlapping reviewers; use panel or hybrid only when model diversity is itself useful.
- R3: focused review and remediation, followed by an `adversarial-verifier`.

Main-agent diff inspection, tests, lint, type checks, and builds are delivery validation, not independent review. Code changes do not automatically require a reviewer.

For staged work, perform one full review after all accepted stages are merged into the integration branch. Add intermediate review only when risk would otherwise compound.

## Waiting and stopping

Continue non-overlapping main-agent work while agents run. A wait timeout means only that the current wait window ended before completion; keep the running agent and wait again later.

Do not interrupt, close, replace, or switch the model of a running agent solely because progress is slow, output is sparse, or a wait timed out. Interrupt or replace it only after an explicit agent error, a user stop or replacement request, an obsolete task, or observable drift or dead state that persists after a non-interrupting correction.

When the user asks to stop, create no new agents and safely collect or close existing work.

## Runtime boundary

The lease, allowed paths, and role instructions are orchestration contracts, not operating-system access controls. The main agent accepts a worker result only after checking the actual diff, task scope, and validation evidence.

The optional `SubagentStart` hook reinforces identity and scope. It does not grant a lease, narrow the sandbox, or replace the task package.
