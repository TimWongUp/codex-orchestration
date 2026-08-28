# Worker write lease

Read this file only when the main agent is about to create a writable worker.

## Admission

In ordinary mode, create a worker only when the task is more than a simple edit, the intended
outcome is settled, the result can be independently accepted, the repository state is ready, and
no other writer is active in this root task. Selecting the writable worker role starts that root
task's lease; while the worker is active, the main agent and every other derived agent remain
read-only. In manager-only mode, the manager-only contract supersedes this threshold: code
implementation, tests, and validation are assigned to `worker` or a method worker.

The worker remains inside the assigned outcome; its profile leaves orchestration, Git, and external
state to the root task. A sandbox or role name does not expand the user's task.

## Worker brief

Use the main Skill's natural-language brief contract. Make the intended change and handoff focus
clear; add exclusions, authority limits, or validation expectations only when they materially
change the work. Let the worker recover ordinary implementation context.

The worker uses judgment to make the smallest complete change, including necessary adjacent files.
It preserves pre-existing work and treats explicit exclusions as binding. If the correct change
would materially expand the requested outcome, conflict with existing changes, or require new
authority, the worker returns a checkpoint instead of guessing.

## Follow-ups and rounds

A branch receives at most three writable rounds: the initial implementation; one same-thread
correction after the worker is idle; then, only when acceptance or Review requires it, one new
worker selected through [model-routing.md](model-routing.md). A round ends when its worker is no
longer running, and no prior lease carries into the next round. In ordinary mode, after round
three the main agent may take over, decompose again, or report the blocker. In manager-only mode,
the main agent must not silently take over. Before three unsuccessful rounds it may re-decompose or
select another worker; after three unsuccessful rounds it may only re-decompose read-only or report
a blocker. Manager-only mode never starts a fourth Worker round or another code-writing round; new
code-writing work waits for a new user direction or the user's explicit consent to exit that mode.

## Handoff and acceptance

The worker returns a natural, concise handoff with the changed files, relevant validation and
results, remaining risks, and any checkpoint that affects acceptance. The repository, complete
diff, and validation output remain the source of truth.

After the worker returns, the main agent inspects the complete diff, confirms that the requested
outcome and pre-existing work were preserved, checks relevant validation, and decides whether the
result is ready for the next stage or review.
