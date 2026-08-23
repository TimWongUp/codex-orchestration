# Use a stateless subagent interruption guard

The former v1 runtime experimented with a stateless guard for `send_input` delivery envelopes and
direct wait results. It intentionally avoided terminal markers and close-order enforcement, but the
guard still coupled installation and validation to a lifecycle API that is no longer active.

**Status:** superseded by [ADR 0007](0007-pure-v2-collaboration-lifecycle.md)

**Decision:** retain this document as historical context only. The guard source, installation
projection, registrations, and active validation were removed during the pure v2 migration. The
current lifecycle contract is expressed by the Skill, the routing and scope Hooks, and the
model-visible v2 tools.

**Consequences:** historical compatibility details are not an active fallback. New orchestration
must use the v2 tool responsibilities and mailbox convergence described in ADR 0007.
