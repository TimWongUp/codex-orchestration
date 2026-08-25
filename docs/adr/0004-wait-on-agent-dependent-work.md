# Wait on agent-dependent work

The main agent waits before any decision, write, or final answer that a pending agent result could
change; it continues only work that is independent, outside the delegated scope, and still useful
under any result, treating uncertainty as a reason to wait. In v2, `wait_agent` waits for updates in
the caller's mailbox rather than returning a target-status map. `list_agents` and final
notifications provide the current tree and status evidence; a missing update is not completion.
We chose this dependency barrier over both unconditional waiting and blanket permission to continue
because it preserves useful concurrency without duplicating delegated work or making results
irrelevant.

**Status:** accepted

**Consequences:** The Skill, public documentation, and tests use the same short
dependency rule and mailbox semantics. Lifecycle calls remain separate model-visible operations;
there is no cross-call status map to cache or reuse.
