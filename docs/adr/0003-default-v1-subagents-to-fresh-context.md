# Default V1 subagents to fresh context

V1 subagents start without the parent conversation by default: ordinary delegation omits `fork_context`, which is equivalent to `fork_context = false`, and the main agent supplies a self-contained task package instead. We chose this over full-history forking because fresh context preserves independent judgment, avoids carrying unrelated conversation into bounded work, and permits selecting a custom agent role; `fork_context = true` inherits the parent role and is reserved for tasks where the parent transcript itself is indispensable.

**Status:** superseded by [ADR 0007](0007-pure-v2-collaboration-lifecycle.md)

**Consequences:** This historical decision no longer defines the active tool schema. The fresh-context
principle remains, but the active contract explicitly passes `fork_turns="none"` to ordinary
`spawn_agent` calls and defines the exceptional full-history inheritance rule in ADR 0007.
