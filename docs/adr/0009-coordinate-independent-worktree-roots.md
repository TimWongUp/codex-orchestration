# Coordinate parallel writing through independent Worktree Roots

**Status:** accepted

## Context

The derived-worker lease deliberately permits one writer inside one root task. That keeps a shared
checkout inspectable, but it serializes implementation even when two or three lanes could be
accepted independently. Giving derived workers descendant orchestration or relying on prompt-only
checkout routing would blur the existing identity boundary without providing official Worktree
isolation. Codex-managed worktrees instead run independent chats in separate checkouts.

## Decision

Parallel writable work uses peer root tasks. When the user explicitly requests official Codex
worktrees and the admission gate passes, one Integration Root may coordinate at most three
nonterminal Worktree Roots created through the current task/thread tools. It refreshes batch state
and reserves each lane slot serially. Each Worktree Root is an independent Codex task and session,
loads the normal orchestration Skill, and may use the ordinary explorer, reviewer, specialist, and
worker roles. The existing derived-agent and per-root single-writer contracts remain unchanged.
The Integration/Worktree distinction is batch scope rather than a separate agent type: a lane root
has normal local orchestration authority, while only the batch's Integration Root manages peers and
cross-lane state.

Every Worktree Root starts from one accepted committed base in a verified distinct official
worktree and returns its task/worktree identity, one candidate handoff branch, commit, complete
diff, validation evidence, and integration risks. The Integration Root waits for every declared
handoff to reach `accepted` before it serially merges lanes into a dedicated integration branch,
runs combined validation, and applies the final R0-R3 review gate to the integrated diff. Failed or
canceled lanes block success; excluding one requires the user's explicit rescoping. Prototype lanes
additionally require explicit user acceptance. Lane review is optional unless risk would otherwise
compound; it never substitutes for the final integrated review.

While any lane is nonterminal, the Integration Root remains repository-read-only. It becomes the
repository writer for serial merge and integration fixes only after the complete batch is accepted.
Until then it neither creates nor retains a local writable-worker lease, and neither its main agent
nor a local worker writes. Therefore no batch has more than three concurrent repository writers.

Each root session may keep at most eight spawned-agent threads open concurrently, excluding its
primary agent, enforced by the host and subject to any lower limit. The three-Worktree-Root limit is
separate because independent tasks do not share one spawned-agent budget. Explicit stop freezes
dispatch, sends the available stop operation or request to every nonterminal peer, and waits for
fresh terminal snapshots; a stopped batch is not merged or delivered as success.

## Consequences

Independent implementation lanes can progress concurrently without granting derived workers
orchestration authority or weakening their lease. The Integration Root cannot directly control a
peer root's descendants and must coordinate through task-level status and messages. Lane overlap,
shared external state, and merge conflicts remain integration risks, so unsafe partitions fall
back to serialized stages. The later retirement of the optional `SubagentStart` Hook does not
change this decision because a Worktree Root is not a derived-agent start event.
