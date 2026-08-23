# Architecture

Codex Orchestration separates five concerns:

1. `SKILL.md` defines main-agent decisions and task-package contracts.
2. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
3. `hooks/` optionally reinforces main-agent routing and derived-agent identity, and guards
   interrupting `send_input` calls.
4. Local preference files select task-package language and models without placing user choices in the repository.
5. `INSTALL.md` defines the reviewed, cross-platform installation contract executed by the user's Agent.

The repository is the single source of truth for portable runtime behavior. Installed Skill,
Agent, and Hook files are replaceable deployment artifacts, while task-package language, model IDs,
executable paths, Hook registrations, and other host choices remain local configuration. This prevents an installed
runtime from becoming a second implementation that drifts independently.

The installed runtime is a projection, not a copy of the repository root: the main Skill receives
only root `SKILL.md` and `references/`; each bundled method Skill has its own Skill destination;
Agent profiles and optional Hook scripts go to Codex home. Deployment registries may record this
repository as authority, but suite installation remains governed by `INSTALL.md` so a generic
single-Skill linker cannot flatten these components or expose the whole checkout as one Skill.

The `skills/diagnosing-bugs` and `skills/prototype` directories contain the complete method Skills loaded by their corresponding writable workers. The Agent profiles retain lease and orchestration boundaries; the method Skills provide the detailed debugging and prototype workflows.

The main agent is the sole orchestrator. Read-only agents may run concurrently. Writable work uses a global single-writer lease: either the main agent writes, or one worker writes inside explicit allowed paths.

Hooks are behavioral guardrails, not a complete authorization or access-control layer. The tool guard blocks unmarked `send_input` interrupts, accepts orchestration corrections only with one of four closed reason codes, and may add advisory context when the host surfaces a direct non-terminal `wait_agent` result. The main agent still owns evidence, bounded use, delegation, result acceptance, user-directed stopping, and close ordering. A correction interrupt may terminate the agent. Each subagent lifecycle call remains a separate model-visible operation; a host that exposes lifecycle tools only through `functions.exec` makes one call per program and returns its result unchanged. Nested wait Hook delivery is not reliable, so the guard does not inspect outer exec results or enforce premature `close_agent`; the Skill requires an explicit terminal entry for that target. Runtime validation rejects stale outer-exec, close, or combined guard registrations. Acceptance depends on the main agent reviewing the real diff and validation evidence.

The three orchestration Hooks stay in this repository because they reinforce the Skill's routing and derived-agent identity contracts and share its tests and validator. `subagent_guard.py` intentionally has no terminal marker or close-agent enforcement; its wait handling is immediate and stateless. Cross-host context injection, memory routing, and closeout behavior belong to their shared runtime instead. A private composition layer may enable both sources on one machine, but it records only paths, deployment mode, and registrations; it does not absorb or redefine either implementation.

Installation is Agent-driven on macOS and native Windows. The repository declares source-to-target intent, conflict policy, one-time source migration, optional choices, and completion criteria instead of reproducing filesystem and configuration logic in a platform-specific installer. `scripts/validate.py` remains read-only and verifies both the public source contract and an installed runtime supplied by path.
