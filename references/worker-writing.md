# Worker write lease

Read this file only when the main agent is about to create a writable worker.

## Admission

Create a worker only when the task is more than a simple edit, the intended outcome is settled,
the result can be independently accepted, the repository state is ready, and no other writer is
active in this root task. Selecting the writable worker role starts that root task's lease; while
the worker is active, the main agent and every other derived agent remain read-only.

Workers are derived agents. They do not load or execute `codex-orchestration`, call collaboration
tools, orchestrate any other agent, manage Git, or change external state. A sandbox or role name is
not permission to expand the user's task.

## Worker brief

Send a compact natural-language brief, not a required form. It normally makes the intended change
and handoff focus clear, supplies only context the worker cannot cheaply recover, and points to
useful files, diffs, logs, or references. Optional headings such as task, context, handoff, and
references may help readability, but their names and presence carry no authority.

Let the worker inspect the repository and recover ordinary implementation context. State explicit
exclusions, authority limits, or validation expectations only when they materially change the
work. Do not create a temporary handoff file for information that fits in the task message.

The worker uses judgment to make the smallest complete change, including necessary adjacent files.
It preserves pre-existing work and treats explicit exclusions as binding. If the correct change
would materially expand the requested outcome, conflict with existing changes, or require new
authority, the worker returns a checkpoint instead of guessing.

## Method workers

`diagnosing-bugs-worker` loads the complete `diagnosing-bugs` Skill and applies its feedback loop,
reproduction, minimization, hypothesis testing, regression-test, and instrumentation-cleanup
method within the assigned outcome.

`prototype-worker` loads the complete `prototype` Skill and builds the smallest throwaway result
that answers the design question without turning it into production architecture on its own.

## Follow-ups and rounds

A follow-up to the same worker thread may contain only the acceptance finding, correction, or new
evidence because the thread retains its context. A newly created worker receives a standalone
brief. The main Skill still limits one branch to three writable rounds; a round ends when that
worker is no longer running, and no prior lease remains active between rounds.

## Handoff and acceptance

The worker returns a natural, concise handoff with the changed files, relevant validation and
results, remaining risks, and any checkpoint that affects acceptance. The repository, complete
diff, and validation output remain the source of truth.

After the worker returns, the main agent inspects the complete diff, confirms that the requested
outcome and pre-existing work were preserved, checks relevant validation, and decides whether the
result is ready for the next stage or review.
