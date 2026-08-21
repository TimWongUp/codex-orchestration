# Wait on agent-dependent work

The main agent waits before any decision, write, or final answer that a pending agent result could change; it continues only work that is independent, outside the delegated scope, and still useful under any result, treating uncertainty as a reason to wait. We chose this dependency barrier over both unconditional waiting and blanket permission to continue because it preserves useful concurrency without duplicating delegated work or making results irrelevant.

**Status:** accepted

**Consequences:** Timeout and terminal-state rules remain unchanged. The Skill, routing Hook, public documentation, and tests use the same short dependency rule.
