# Architecture

Codex Orchestration separates five concerns:

1. `SKILL.md` defines main-agent decisions, the collaboration lifecycle, and task-package
   contracts.
2. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
3. `hooks/` optionally reinforces the writable-worker lease check.
4. Local preference files select task-package language and models without placing user choices in
   the repository.
5. `INSTALL.md` defines the reviewed, cross-platform installation contract executed by the user's
   Agent.

The repository is the single source of truth for portable runtime behavior. Installed Skill,
Agent, and Hook files are replaceable deployment artifacts, while task-package language, model
IDs, executable paths, Hook registrations, and other host choices remain local configuration.
This prevents an installed runtime from becoming a second implementation that drifts
independently.

The installed runtime is a projection, not a copy of the repository root: the main Skill receives
only root `SKILL.md` and `references/`; each bundled method Skill has its own Skill destination;
Agent profiles and optional Hook scripts go to Codex home. Deployment registries may record this
repository as authority, but suite installation remains governed by `INSTALL.md` so a generic
single-Skill linker cannot flatten these components or expose the whole checkout as one Skill.

The `skills/diagnosing-bugs` and `skills/prototype` directories contain the complete method Skills
loaded by their corresponding writable workers. The Agent profiles retain lease and orchestration
boundaries; the method Skills provide the detailed debugging and prototype workflows.

The main agent is the sole orchestrator. Read-only agents may run concurrently. Writable work uses
a global single-writer lease: either the main agent writes, or one worker writes inside explicit
allowed paths.

Read-only collaboration has three multi-agent evaluation modes. `coverage` assigns non-overlapping
evidence or risk areas. `panel` gives the same core question to distinct models. `hybrid` combines
one such panel with separate specialist workstreams when both independent model judgment and
non-overlapping risk coverage can change the decision. The ordinary `single` path creates one
agent and is not an evaluation mode. Only the panel path classifies the parent model; coverage and
hybrid's specialist workstreams use ordinary role routes.

## V2 lifecycle

The model-visible collaboration-tool schemas own call mechanics. The repository does not wrap the
tools or cache their API descriptions. Its portable policy starts ordinary delegation with
`fork_turns="none"` and a self-contained task package; bounded transcript context is an explained
exception.

The main agent waits before any decision, write, or final answer that pending work could change,
while continuing only independent work. The current tree and final notification are the
authoritative convergence signals. After a follow-up is accepted, earlier final notifications and
snapshots for that target are stale, so the main agent waits for a newer final and reconciles it
with a fresh snapshot. A third writable round creates a new agent with a fresh package and lease.

An explicit stop freezes new delegation, snapshots the tree, interrupts every active descendant,
and waits for final notifications plus a fresh snapshot showing no running agents. A leased worker
retains its lease until that convergence point. A correction that must prevent further current-turn
work first interrupts the target and waits for the interruption to become visible, then uses
`followup_task` to deliver the corrected task.

The `SubagentStart` Hook stays in this repository because it reinforces the writer-lease contract
and shares its tests and validator. Agent profiles remain the authority for derived-agent identity
and read-only scope. Main-agent orchestration policy remains in the Skill and current tool schemas,
so no `UserPromptSubmit` route reminder is installed. Cross-host context injection, memory routing,
and closeout behavior belong to their shared runtime; Codex-native agent status UI remains
host-owned.

Installation is Agent-driven on macOS and native Windows. The repository declares source-to-target
intent, conflict policy, one-time source migration, optional choices, and completion criteria
instead of reproducing filesystem and configuration logic in a platform-specific installer.
`scripts/validate.py` remains read-only and verifies both the public source contract and an
installed runtime supplied by path.
