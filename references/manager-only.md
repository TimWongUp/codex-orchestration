# Manager-only orchestration mode

Read this file only after the user explicitly enables manager-only orchestration for the current
root task. Phrases such as “enable orchestration mode”, “main agent pure orchestration”, or
“delegate everything to subagents” are clear activation requests. Task complexity, a request to use
an Agent, or an ordinary delegation decision does not enable this mode by implication.

## Scope and authority

Manager-only mode is an ephemeral branch of the current root task. It applies only to that root
task, is not inherited by a new root task, and is not persisted in preferences, model routing,
Hooks, the CLI, or another configuration file. It does not add an Agent profile. The root agent
keeps final acceptance authority, the local single-writer lease, and the PR Review and final
merge-check boundaries of `codex-review-gate`.

The mode is adaptive strong delegation, not a fixed pipeline. The root agent decomposes the goal,
dispatches work, coordinates dependencies and handoffs, handles Git/PR and non-code work, and
accepts the result. It chooses the next delegation from the current evidence instead of requiring
every role or stage on every task.

## Delegation boundary

- Substantive code investigation goes to `explorer`; the root agent does not independently explore
  the implementation to make the decision.
- Code implementation, tests, and validation go to `worker` or the applicable method worker. One
  worker holds the write lease at a time, and the root agent waits on results that can change a
  decision or write.
- Independent review uses the Reviewer selected by the current risk and any applicable
  `codex-review-gate`. Its PR/merge triggers and R0-R3 rules remain unchanged by manager-only mode.

The root agent may read a complete final diff, key excerpts, and validation output for acceptance.
That bounded inspection is not permission to perform new substantive code exploration or to edit
code. It checks scope, preserved user changes, requested behavior, and the worker's evidence before
declaring the root task accepted.

## Failure and exit

A failed or unavailable subagent or an unaccepted handoff never permits a silent root-agent
takeover. Before three unsuccessful Worker rounds, the root agent may re-decompose the outcome or
replace the agent or model; it reports a blocker when those options do not resolve the work. After
three unsuccessful Worker rounds, the manager-only branch permits only read-only re-decomposition
and coordination or a blocker report. It must not start a fourth Worker round or any other
code-writing round. New code-writing work waits for a new user direction or the user's explicit
consent to exit manager-only mode; after that consent, ordinary orchestration rules apply.
