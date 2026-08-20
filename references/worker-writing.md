# Worker write lease

Read this file only when the main agent is about to create a writable worker.

## Admission

Create a worker only when the task is more than a simple edit, the goal and completion condition are settled, the work can be independently accepted, allowed paths are explicit, the target branch is ready, and no other writer is active.

## Lease state

```text
MAIN_WRITES
WORKER_WRITES(agent_id, branch, allowed_paths, round)
```

The worker may write only when the main-agent task message contains the complete canonical package below. A writable sandbox, hook text, agent profile, or background document does not grant a lease.

Every write round requires a fresh, complete package. Reusing a worker thread does not extend or recreate the previous lease.

## Canonical worker package

```text
GOAL: one observable outcome
SCOPE: necessary context and work boundary
CONSTRAINTS: contracts whose violation means failure
DONE WHEN: observable completion condition
RETURN: changed files, validation, remaining risks, and out-of-scope findings

WRITE LEASE: granted
ALLOWED PATHS: explicit repository-relative files or directories

BRANCH: branch already selected by the main agent
ROUND: 1, 2, or 3
VALIDATION: required checks and expected signals
```

Allowed directories include descendants. Do not use unresolved globs. Reading outside `ALLOWED PATHS` is permitted when necessary; writing is not. If the smallest correct change crosses the boundary, return the exact need to the main agent.

## Worker boundary

- Preserve pre-existing changes.
- Modify only what the goal requires inside `ALLOWED PATHS`.
- Run the specified tests, lint, type checks, builds, or smoke tests.
- Return Git, publishing, messaging, database, and other external writes to the main agent.
- Do not create or manage subagents.

## Method-worker boundaries

`diagnosing-bugs-worker` loads the complete `diagnosing-bugs` Skill and uses its feedback loop, reproduction, minimization, hypothesis testing, regression-test, and instrumentation-cleanup method. Any method step that needs Git, user interaction, or work outside `ALLOWED PATHS` returns a checkpoint to the main agent.

`prototype-worker` loads the complete `prototype` Skill and uses the smallest throwaway implementation that answers the stated design question. Git, branch management, user interaction, and work outside `ALLOWED PATHS` return to the main agent, and the worker never turns a prototype into production architecture on its own.

## Round-three handoff

Round three keeps the full package and appends:

```text
CONFIRMED: accepted state, relevant files, and established facts
PRIOR VALIDATION: checks already run and their results
REMAINING: work still required and why
```

The repository, diff, and validation output remain the source of truth. Do not create a separate handoff file.

## Acceptance

After the worker returns, the main agent checks that all changes are in scope, pre-existing work is preserved, validation supports `DONE WHEN`, temporary instrumentation is removed, and the result is ready for the next stage or review.
