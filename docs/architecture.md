# Architecture

Codex Orchestration separates four concerns:

1. `SKILL.md` defines main-agent decisions and task-package contracts.
2. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
3. `hooks/` optionally reinforces main-agent routing and derived-agent identity.
4. A local model-routing file selects models without placing machine-specific IDs in the repository.

The `skills/diagnosing-bugs` and `skills/prototype` directories contain the complete method Skills loaded by their corresponding writable workers. The Agent profiles retain lease and orchestration boundaries; the method Skills provide the detailed debugging and prototype workflows.

The main agent is the sole orchestrator. Read-only agents may run concurrently. Writable work uses a global single-writer lease: either the main agent writes, or one worker writes inside explicit allowed paths.

Hooks are reminders, not authorization. Agent files are behavioral configuration, not a complete access-control layer. Acceptance depends on the main agent reviewing the real diff and validation evidence.

The repository is macOS-only in its first release. Platform-specific installation behavior is intentionally isolated in `scripts/install.py` so a future Windows adapter can be added without forking the orchestration contract.
