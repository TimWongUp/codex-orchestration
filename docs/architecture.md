# Architecture

Codex Orchestration separates five concerns:

1. `SKILL.md` defines main-agent decisions and task-package contracts.
2. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
3. `hooks/` optionally reinforces main-agent routing and derived-agent identity, and guards the
   two tool actions that can prematurely terminate running subagents.
4. A local model-routing file selects models without placing machine-specific IDs in the repository.
5. `INSTALL.md` defines the reviewed, cross-platform installation contract executed by the user's Agent.

The repository is the single source of truth for portable runtime behavior. Installed Skill,
Agent, and Hook files are replaceable deployment artifacts, while model IDs, executable paths,
Hook registrations, and other host choices remain local configuration. This prevents an installed
runtime from becoming a second implementation that drifts independently.

The installed runtime is a projection, not a copy of the repository root: the main Skill receives
only root `SKILL.md` and `references/`; each bundled method Skill has its own Skill destination;
Agent profiles and optional Hook scripts go to Codex home. Deployment registries may record this
repository as authority, but suite installation remains governed by `INSTALL.md` so a generic
single-Skill linker cannot flatten these components or expose the whole checkout as one Skill.

The `skills/diagnosing-bugs` and `skills/prototype` directories contain the complete method Skills loaded by their corresponding writable workers. The Agent profiles retain lease and orchestration boundaries; the method Skills provide the detailed debugging and prototype workflows.

The main agent is the sole orchestrator. Read-only agents may run concurrently. Writable work uses a global single-writer lease: either the main agent writes, or one worker writes inside explicit allowed paths.

Hooks are behavioral guardrails, not a complete authorization or access-control layer. The tool guard blocks unmarked interrupts and closes without an observed terminal status, while the main agent still owns delegation, result acceptance, and user-directed stopping. Acceptance depends on the main agent reviewing the real diff and validation evidence.

Installation is Agent-driven on macOS and native Windows. The repository declares source-to-target intent, conflict policy, one-time source migration, optional choices, and completion criteria instead of reproducing filesystem and configuration logic in a platform-specific installer. `scripts/validate.py` remains read-only and verifies both the public source contract and an installed runtime supplied by path.
