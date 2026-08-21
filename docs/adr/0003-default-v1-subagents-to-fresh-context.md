# Default V1 subagents to fresh context

V1 subagents start without the parent conversation by default: ordinary delegation omits `fork_context`, which is equivalent to `fork_context = false`, and the main agent supplies a self-contained task package instead. We chose this over full-history forking because fresh context preserves independent judgment, avoids carrying unrelated conversation into bounded work, and permits selecting a custom agent role; `fork_context = true` inherits the parent role and is reserved for tasks where the parent transcript itself is indispensable.

**Status:** accepted

**Consequences:** Main-agent instructions do not require an explicit `fork_context = false` argument because omission already expresses the default with less tool-schema overhead. Independent exploration, coverage, review, and writable-role delegation rely on the task package rather than parent history. A caller may set `fork_context = true` only when continuing the existing conversation matters more than role specialization and contextual isolation; indispensable facts produced during the current parent turn must still be placed in the task package rather than assumed to be inherited.
