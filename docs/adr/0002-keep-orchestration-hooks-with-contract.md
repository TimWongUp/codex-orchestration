# Keep orchestration Hooks with the orchestration contract

`orchestration_route.py` and `subagent_scope.py` remain in `codex-orchestration` because they
reinforce this Skill's routing and derived-agent identity contracts and are verified by the same
tests and validator. Shared context, memory-routing, and closeout Hooks remain in their cross-host
runtime; private machine composition may register both sources without moving or redefining either
implementation.

**Status:** accepted

**Supersedes:** the retired lifecycle guard portion of the original decision; the pure v2 lifecycle
boundary is recorded in [ADR 0007](0007-pure-v2-collaboration-lifecycle.md).

**Consequences:** orchestration Hook changes are reviewed and released with the Skill contract, and
installation preserves unrelated shared-runtime registrations. Machine paths or enablement
choices stay outside the public repository. The Hooks do not become a second lifecycle
implementation: v2 tool semantics remain in the Skill and model-visible tools.
