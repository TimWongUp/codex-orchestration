# Keep portable runtime behavior in the repository

The public repository is the sole source of truth for its portable Skill, Agent, validation behavior,
and the orchestration Hook `subagent_scope.py`; installed files
are replaceable deployment artifacts, while model routes, executable paths, Hook registrations, and
other host choices remain local. Shared context, memory-routing, and closeout Hooks remain owned by
their runtime repository. We chose this over maintaining a separately editable personal Skill
because dual implementations had already drifted and made ordinary requests ambiguous.

**Status:** accepted

**Consequences:** Changes start in a repository branch, pass source review and tests, then deploy to the runtime through `INSTALL.md`. The runtime is a component projection rather than the repository root treated as one Skill. External deployment registries may record this repository as authority but must defer suite writes to the installation contract. Local configuration may select models or wire Hooks but must not redefine portable behavior. Replacing an older linked or copied source is an explicit one-time cutover, and retiring that old source remains a separate user decision.
