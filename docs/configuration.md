# Configuration

## Authority boundary

Portable orchestration behavior is edited and reviewed in this repository. Installed Skill,
Agent, and global-rule files are deployment artifacts and should not be edited directly. Host-specific
task-package language, model routes, and unrelated Hook registrations remain outside Git so one repository
can serve different machines without publishing private paths or model identifiers.

## Install scope

Interactive user installation defaults to `~/.codex` and the documented user Skill root
`~/.agents/skills`. Non-standard runtimes pass explicit targets after inspecting their current
configuration and installed Skill listings. Managed destinations are:

- `<skills-root>/codex-orchestration` — the main Skill copy.
- `<skills-root>/codex-review-gate` — the independent delivery Review policy copy.
- `<skills-root>/diagnosing-bugs` — the bundled complete debugging Skill copy.
- `<skills-root>/prototype` — the bundled complete prototype Skill copy.
- `<codex-home>/agents/*.toml` — managed custom-agent copies.
- `<codex-home>/codex-orchestration/preferences.toml` — only when a task-package language is
  saved.
- `<codex-home>/codex-orchestration/model-routing.toml` — only when local routing is approved.
- The active `<codex-home>/AGENTS.override.md` or `<codex-home>/AGENTS.md` — only the canonical
  marker-delimited orchestration and code Review block.

`INSTALL.md` is the authority for path discovery, planning, conflict handling, optional choices,
and verification. `scripts/install.py` implements it and always prints the complete plan before a
write. Interactive terminals require confirmation; non-interactive runs write only with
`--apply`. Installation creates copies rather than links so the same contract works on macOS and
native Windows. Existing symlinks and non-directory parents are conflicts: setup does not traverse,
unlink, replace, or write through them. Unrelated files and Hook registrations are preserved.

Externally owned registrations and deployment metadata are reported with their owning runtime or
registry and left untouched. They are outside the `current`, `missing`, `drift`, and `conflict`
states used for managed installation targets.

## Existing Skill preflight

All four Skill targets are checked before any installation write:

- An exact source copy is `current`.
- A missing Skill is planned for creation.
- A same-named but different Skill, a symlink, a non-directory Skill target, or a non-directory
  parent is a conflict and remains untouched.

Managed Agent, preference, and routing targets are classified the same way. Differing
managed files are drift. The Agent shows the difference and replaces it only after explicit
approval; conflicts are left for the user to resolve without deletion.

Those rules govern ordinary installation. During a one-time migration from another source,
`INSTALL.md` section 7 is authoritative: after the user approves the exact cutover targets, the
Agent may remove only the confirmed managed links before installing the physical runtime
projection. Old source directories are still retained unless the user separately approves their
retirement.

## Unmanaged legacy assets

The installer and runtime validator own only the current named projection. They do not inspect
`hooks.json`, the Hook directory, or extra Agent profiles, including files left by earlier project
versions. This keeps the installation plan write-only and prevents historical cleanup rules from
becoming a permanent parser for user-owned configuration.

When legacy cleanup is desired, treat it as a separate maintenance task: inspect the live runtime,
resolve the exact files and registrations, show the removal plan, and obtain explicit approval.
Installing or validating the current projection neither proves that cleanup is needed nor claims it
has happened.

## V2 collaboration boundary

The model-visible collaboration-tool schemas own call mechanics. This repository does not wrap
those tools, cache their return shapes, or define a transport fallback. `codex-orchestration` adds
only orchestration policy: ordinary delegation uses `fork_turns="none"`, pending results form a
dependency barrier, a follow-up invalidates earlier completion evidence, an explicit stop converges
the active tree, and a third worker round starts with a fresh package and lease.

This project installs no Hook. Agent profiles own derived-agent identity and read-only scope;
`codex-orchestration` owns root-task Agent execution, while `codex-review-gate` defines the delivery
Review route and Reviewer authorization. The root main agent executes classification, remediation,
verification, and delivery, and main-agent acceptance checks the complete worker diff and
validation. Delegation uses compact natural-language briefs instead of fixed authorization fields.

## Concurrency and Worktree Roots

The portable policy permits at most eight concurrently open spawned-agent threads in each root
session, excluding its primary agent. Configure Codex with the corresponding host-enforced session
cap:

```toml
[agents]
max_concurrent_threads_per_session = 8
```

A lower host or workspace limit wins. Before a spawn, each root confirms the enforced cap, refreshes
the visible agent tree when available, and never intentionally exceeds the lower limit. If the cap
cannot be confirmed, the root fails closed and does not spawn; a missing count or rejection is not
bypassed. Independent Worktree Roots have separate sessions and do not consume the Integration
Root's spawned-agent slots, so this setting is not a machine-wide global cap.

Official Worktree Roots are a separate task-level feature. They require the user's current explicit
request, a Git repository, the admission gate in `references/worktree-roots.md`, and current
task/thread tools that can create a worktree environment and expose enough identity to verify
distinct checkouts. One Integration Root serially reserves at most three nonterminal lane slots;
pending and running tasks consume a slot until terminal. Each Worktree Root runs the ordinary
root-task contract and may use the installed custom Agent profiles; no special Worktree Agent
profile or Hook registration is installed.

## Global instructions

`examples/global-agents-block.md` is the single source of truth for the always-loaded orchestration
and code Review pointers. Setup enables it by default and selects the first non-empty global
instruction file using
Codex precedence: `AGENTS.override.md`, then `AGENTS.md`. Only the exact marker-delimited block is
managed. Surrounding content and line endings are preserved, and a change in the active target
moves the block so two copies cannot load at different times.

Nested, unmatched, duplicated, or non-standalone marker tokens are conflicts.
`--no-global-rules` leaves existing global files unchanged; it is not an uninstall operation. A
managed block that already exists must match the current canonical block, so this option cannot
silently combine new Skills with stale Review routing. The full workflows stay in their Skills to
keep global context small. The Review pointer requires `codex-review-gate` after repository
implementation, test, dependency, build/deployment, public-contract, or managed runtime-policy changes and
authorizes only its R1-R3 read-only Reviewers. Ordinary proactive-delegation admission cannot
suppress those Reviewer calls, while implementation and investigation delegation retain their
normal threshold.

## Delivery review

`codex-review-gate` classifies the final integrated diff before delivery. R0 covers only mechanical,
non-behavioral, fully verifiable changes; R1 covers one localized, validated, recoverable risk,
including local runtime, test-semantic, dependency, or build changes; R2 covers cross-module,
public-contract, sensitive-boundary, multiple independent, or otherwise unclassified risk; R3
covers changed trust or authorization boundaries and high-impact failure. The highest matching
level wins, diff size alone never decides the level, and uncertainty fails closed to the higher
level or R2 fallback.

R0 uses main-agent inspection and validation only. R1 uses one Reviewer for the most material risk,
R2 uses two non-overlapping Reviewers, and R3 performs focused Review and main-agent remediation
before an `adversarial-verifier`. Review Agent execution reuses `codex-orchestration`; the Review
Skill does not duplicate model routing, lifecycle, or waiting policy.

Each normal Reviewer stays within its assigned change boundary and risk. When a finding depends on
a task or spec requirement or a repository standard, the Reviewer cites that source and identifies
the evidence class without starting a generic Standards/Spec pass. Labelled judgment calls remain
distinct, and Reviewers omit checks conclusively covered by current passing tooling unless the
tool's coverage or evidence is itself part of the assigned risk.

## Task-package language

An explicit language request wins. Otherwise the main Skill reads
`<codex-home>/codex-orchestration/preferences.toml` when present. Supported persisted values are
`en` and `zh-CN`; without the file, task-package prose follows the current user's language.

The preference changes delegation prose and the requested return language only. Role names, paths,
and literals defined by external tools or protocols remain unchanged. Installation starts from
`examples/preferences.toml`, shows the selected file, and preserves an existing valid preference
unless the user approves a change.

## Model routes

The repository does not ship active routes. Start from `examples/model-routing.toml`, replace
placeholders with values available on the current host, and review the full order and host
requirements before approving the Agent's write. Schema version 2 separates ordinary role routes
from parent-aware panel rosters.

Optional `task_overrides` entries prepend one local model and reasoning-effort configuration for a
clearly named task kind and a bounded list of roles. Explicit user choices still win; unmatched
tasks use the ordinary role route, and unavailable override models fall back to that role's first
available entry. Ordinary `single`, `coverage`, worker, and Hybrid specialist delegation do not
inspect the parent model. A `worker-round-three` override may cover every writable role; without a
usable match, round three takes the next distinct available entry after round one's model. If none
exists, the main agent takes over, decomposes again, or reports the blocker.

`panel_routes.gpt` and `panel_routes.third_party` are used only by `panel` and the panel workstream
in `hybrid`; a Hybrid brief makes the panel/specialist distinction clear when routing needs it.
The latest host-generated system or developer model binding selects the family; missing or
ambiguous identity fails closed to the GPT family. Each family marks entries as `primary` or
`fallback`. An explicit user model may occupy one seat, while ordinary task overrides do not apply
to Panel. A completed Panel needs at least two distinct usable models; otherwise it is reported as
unavailable or degraded rather than silently changing families.

Every task, panel, and role entry includes `service_tier = "priority"` or `"standard"`. This is a
host requirement rather than a collaboration-tool argument. The Agent must verify that the host
can enforce it for that model and must skip an entry whose requirement conflicts with an
unavoidable global tier.

Without a local route file, omitting model selection requests inheritance from the current Codex
configuration; it does not confirm the resolved model. Runtime validation parses a saved route and
rejects malformed fields, placeholders, duplicate family models, or a Panel family with fewer than
two distinct primaries.

## Verification

```text
python scripts/validate.py
python scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root>
python scripts/validate.py --runtime --global-rules --codex-home <codex-home> --skills-root <skills-root>
```

Use the interpreter command available on the host. `--skills-root` is required so validation
cannot guess a non-active location. Runtime validation checks exact bundled Skill and Agent copies,
validates any saved task-package language and model route, and rejects linked managed targets. It
ignores unmanaged Agent and Hook assets. Add `--global-rules` when the managed block was selected;
it checks the active Codex global instruction file and rejects stale copies in the inactive file.
The installing Agent separately verifies that the host can enforce each approved model route entry.
