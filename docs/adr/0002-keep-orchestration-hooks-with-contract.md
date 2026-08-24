# Keep only the writer-lease Hook with the orchestration contract

`subagent_scope.py` remains in `codex-orchestration` because a spawn-time check for the complete
writer lease is a small, safety-relevant reinforcement of the Skill contract. Read-only identity,
scope, and panel rules stay in Agent profiles. Shared context, memory-routing, and closeout Hooks
remain in their cross-host runtime.

The former `UserPromptSubmit` route Hook is retired. Main-agent routing and lifecycle policy already
arrive through the Skill, repository instructions, and current model-visible collaboration-tool
schemas; injecting them again on every user prompt added context load and duplicated authorities.
Codex-native agent status and notification behavior remains host-owned.

**Status:** accepted

**Supersedes:** the retired lifecycle guard portion of the original decision; the pure v2 lifecycle
boundary is recorded in [ADR 0007](0007-pure-v2-collaboration-lifecycle.md).

**Consequences:** writer-lease Hook changes are reviewed and released with the Skill contract, and
installation preserves unrelated shared-runtime registrations. Machine paths and enablement stay
outside the public repository. Installation removes confirmed prior project Route copies and
registrations; ambiguous or external assets remain conflicts. The Hook does not become a second
lifecycle or identity implementation.
