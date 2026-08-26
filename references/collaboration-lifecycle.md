# Collaboration lifecycle

Read this file when coordinating a follow-up, interruption, replacement, slow or sparse agent, or
an explicit stop. Current collaboration-tool schemas are the sole authority for call mechanics.
An ordinary final notification is sufficient for a normal dependency wait. Take a fresh snapshot
only where a branch below expressly requires one after a follow-up, interruption, replacement, or
stop.

## Follow-ups

A same-thread follow-up contains only the correction, question, or new evidence because the thread
keeps its accepted context. A new agent receives a standalone brief.

After `followup_task` is accepted, every earlier final notification and status snapshot for that
target is stale. Wait for a newer final notification and reconcile it with a fresh agent-tree
snapshot before using the result.

## Guidance and interruption

Slow progress, sparse output, or a wait with no update does not justify guidance, interruption,
replacement, or a model switch. Leave useful current work running.

When new guidance can affect the result, send it with the operation that matches its meaning. Use
`interrupt_agent` only when the current turn must stop before a correction can safely apply. Wait
until the interruption appears in a final notification or fresh status, then submit the correction
with `followup_task`.

Replacing an agent ends any active write lease only after the old worker is no longer running. A
new writable round receives a new lease and standalone brief; no prior lease is extended.

## Stop convergence

When the user explicitly stops subagent work:

1. Freeze new delegation and take a fresh agent-tree snapshot.
2. Interrupt every active descendant.
3. Wait for new final notifications and another fresh snapshot proving none remain running.
4. End a worker lease only after its worker is no longer running.

For a Worktree batch, also follow `references/worktree-roots.md`: freeze peer dispatch, stop active
peers with current task/thread capabilities, cancel unaccepted lanes, and wait for every peer and
lane to become terminal. If the host cannot force-stop a peer, report the limitation and keep the
batch stopped; do not merge or claim convergence.
