# Codex Orchestration Context

This context defines the project-specific language used to distinguish independent Codex tasks
from agents derived inside one task.

## Language

**Integration Root**:
The root Codex task that coordinates independent worktree lanes and owns the merged state, final
review, and integrated outcome.
_Avoid_: parent agent, integration worker

**Worktree Root**:
An independent root Codex task and session operating in its own Codex-managed Git worktree, with
the same local orchestration authority as any root task. It is a peer root task, not a derived
writable agent; while assigned one lane, it cannot take over its Integration Root's batch scope.
_Avoid_: Worktree Writer, worktree subagent

**Derived Agent**:
An agent created inside one root task and governed by that root task's orchestration authority.
_Avoid_: child root, nested root

**Delivery Review**:
The mandatory root-task quality gate applied before delivery to a final diff that changes
repository implementation, tests, dependencies, build/deployment configuration, public contracts, or managed
runtime policy. It is separate from ordinary delegation admission and may use read-only Reviewer
Agents as its execution mechanism.
_Avoid_: implementation delegation, proactive delegation
