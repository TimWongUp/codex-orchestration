# Architecture

Codex Orchestration separates five concerns:

1. `SKILL.md` defines main-agent decisions and task-package contracts.
2. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
3. `hooks/` optionally reinforces main-agent routing and derived-agent identity.
4. A local model-routing file selects models without placing machine-specific IDs in the repository.
5. `INSTALL.md` defines the reviewed, cross-platform installation contract executed by the user's Agent.

The `skills/diagnosing-bugs` and `skills/prototype` directories contain the complete method Skills loaded by their corresponding writable workers. The Agent profiles retain lease and orchestration boundaries; the method Skills provide the detailed debugging and prototype workflows.

The main agent is the sole orchestrator. Read-only agents may run concurrently. Writable work uses a global single-writer lease: either the main agent writes, or one worker writes inside explicit allowed paths.

Hooks are reminders, not authorization. Agent files are behavioral configuration, not a complete access-control layer. Acceptance depends on the main agent reviewing the real diff and validation evidence.

Installation is Agent-driven on macOS and native Windows. The repository declares source-to-target intent, conflict policy, optional choices, and completion criteria instead of reproducing filesystem and configuration logic in a platform-specific installer. `scripts/validate.py` remains read-only and verifies both the public source contract and an installed runtime supplied by path.
