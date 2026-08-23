# Keep orchestration Hooks with the orchestration contract

`orchestration_route.py`, `subagent_scope.py`, and `subagent_guard.py` remain in `codex-orchestration` because they reinforce this Skill's routing, derived-agent identity, and tool-control contracts and are verified by the same tests and validator. Shared context, memory-routing, and closeout Hooks remain in their cross-host runtime; private machine composition may register both sources without moving or redefining either implementation.

**Status:** accepted

**Superseded in part by:** ADR 0006 removes terminal-marker and close-order enforcement from `subagent_guard.py` while retaining the Hook suite in this repository.

**Consequences:** orchestration Hook changes are reviewed and released with the Skill contract, installation preserves unrelated shared-runtime registrations, and machine paths or enablement choices stay outside the public repository. This avoids both a monolithic Hook repository detached from the behavior it guards and private deployment details leaking into portable source.
