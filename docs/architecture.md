# Architecture

Codex Orchestration separates five concerns:

1. `SKILL.md` defines main-agent decisions, the collaboration lifecycle, and task-package
   contracts.
2. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
3. `hooks/` optionally reinforces main-agent routing and derived-agent identity.
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

## V2 lifecycle

`spawn_agent` creates a fresh-context agent when called with `fork_turns="none"`, the ordinary
delegation default. A positive value carries bounded partial history and may combine model or
reasoning-effort overrides. Omitting `fork_turns` or using `"all"` carries full history, inherits
the parent model and reasoning effort, and rejects those overrides. `send_message` queues supplemental information to an existing agent and
does not start a turn. `followup_task` assigns subsequent work to an existing non-root agent after
it is running at the next message boundary or after a pending tool call, and triggers a new turn
when the target is idle. `wait_agent` waits for the caller's mailbox, while
`list_agents` and final notifications reconcile the current tree and statuses. `interrupt_agent`
interrupts an active turn without discarding its context.

The main agent waits before any decision, write, or final answer that pending work could change,
while continuing only independent work. A missing mailbox update is not completion; the current
tree and final notification are the authoritative convergence signals. After a follow-up is
accepted, earlier final notifications and snapshots for that target are stale, so the main agent
waits for a newer final and reconciles it with a fresh snapshot. Each lifecycle call is a separate
model-visible operation; when a host exposes the tools only through `functions.exec`, one call is
made per program and its structured result is returned unchanged. A third writable round creates a
new agent with a fresh package rather than closing an old thread.

An explicit stop freezes new delegation, snapshots the tree, interrupts every active descendant,
and waits for final notifications plus a fresh snapshot showing no running agents. A leased worker
retains its lease until that convergence point. A correction that must prevent further current-turn
work first interrupts the target and waits for the interruption to become visible, then uses
`followup_task` to deliver the corrected task.

The two orchestration Hooks stay in this repository because they reinforce the Skill's routing and
derived-agent identity contracts and share its tests and validator. Cross-host context injection,
memory routing, and closeout behavior belong to their shared runtime instead. A private
composition layer may enable both sources on one machine, but it records only paths, deployment
mode, and registrations; it does not absorb or redefine either implementation.

Installation is Agent-driven on macOS and native Windows. The repository declares source-to-target
intent, conflict policy, one-time source migration, optional choices, and completion criteria
instead of reproducing filesystem and configuration logic in a platform-specific installer.
`scripts/validate.py` remains read-only and verifies both the public source contract and an
installed runtime supplied by path.
