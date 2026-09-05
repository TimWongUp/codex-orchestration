# Codex Orchestration Context

This context defines the project-specific language used to distinguish independent Codex tasks
from agents derived inside one task.

## Language

**Integration Root**:
The root Codex task that coordinates independent worktree lanes and owns the accepted integration
branch and combined validation. It owns PR Review when handling that PR, and Pre-merge Review
when it also owns the primary-branch merge.
_Avoid_: parent agent, integration worker

**Worktree Root**:
An independent root Codex task and session operating in its own Codex-managed Git worktree, with
the same local orchestration authority as any root task. It is a peer root task, not a derived
writable agent; while assigned one lane, it cannot take over its Integration Root's batch scope.
_Avoid_: Worktree Writer, worktree subagent

**Derived Agent**:
An agent created inside one root task and governed by that root task's orchestration authority.
_Avoid_: child root, nested root

**Manager-only mode**:
An explicit, current-root-task-only branch in which the root agent decomposes, dispatches, and
accepts work while substantive code investigation goes to `explorer` and code implementation,
tests, and validation go to a leased `worker` or method worker. It is adaptive rather than a fixed
pipeline, does not persist, and does not permit silent root-agent takeover after a failed agent.
After three unsuccessful Worker rounds, it allows only read-only re-decomposition or a blocker
report; new code writing waits for a new user direction or explicit exit. Leaving it requires the
user's explicit consent.
_Avoid_: default orchestration, persistent manager mode, mandatory pipeline

**PR Review**:
Risk-based assessment of a pinned PR candidate, started after creation or update or on an explicit
review request, independently of CI availability.
_Avoid_: merge authorization, automatic repository monitoring

**Pre-merge Review**:
The final check that valid risk Review and required validation cover the latest pinned candidate diff before it enters the primary branch; it may reuse an earlier PR Review.
_Avoid_: implementation delegation, proactive delegation
