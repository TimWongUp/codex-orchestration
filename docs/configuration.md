# Configuration

## Authority boundary

Portable orchestration behavior is edited and reviewed in this repository. Installed Skill,
Agent, and global-rule files are deployment artifacts and should not be edited directly. Host-specific
task-package language, model routes, and unrelated Hook registrations remain outside Git so one repository
can serve different machines without publishing private paths or model identifiers.

## Install scope

Interactive user installation defaults to `~/.codex` and its `skills` directory
(`~/.codex/skills`). An explicit or environment-selected Codex home uses its own `skills`
directory unless `--skills-root` overrides it. Non-standard runtimes pass explicit targets after
inspecting their current configuration and installed Skill listings. Managed destinations are:

- `<skills-root>/codex-orchestration` — the main Skill copy.
- `<skills-root>/codex-review-gate` — the independent PR Review and final merge-check policy copy.
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
Every installation plan also reports whether local model routing is valid, absent, or conflicting.
With no route, subagents request inheritance from current Codex settings; this does not confirm the
resolved model. The installer does not invent host-specific routes; an installing Agent offers the
optional configuration flow described below after live verification.

Externally owned registrations and deployment metadata are reported with their owning runtime or
registry and left untouched. They are outside the `current`, `missing`, `drift`, and `conflict`
states used for managed installation targets.

## Existing Skill preflight

All listed Skill targets are checked before any installation write:

- An exact source copy is `current`.
- A missing Skill is planned for creation.
- A same-named but different Skill, a symlink, a non-directory Skill target, or a non-directory
  parent is a conflict and remains untouched.

Managed Agent and preference targets are classified the same way. Differing managed files are
drift. The Agent shows the difference and replaces it only after explicit approval; conflicts are
left for the user to resolve without deletion. Local model routing is not a managed projection:
setup preserves a valid route, reports an absent route, and treats a linked, non-file, unreadable,
or invalid route as a conflict without replacing it.

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

### Explicit manager-only mode

Manager-only mode is enabled only by a clear user request such as “enable orchestration mode”, “main
agent pure orchestration”, or “delegate everything to subagents”. It applies to the current root
task only and is not persisted in preferences, model routing, Hooks, the CLI, or another
configuration file. Read [references/manager-only.md](../references/manager-only.md) for the full
activation, adaptive delegation, acceptance, failure, and explicit-exit contract.

In this mode the root agent decomposes and coordinates adaptively, sends substantive code
investigation to `explorer`, and sends code implementation, tests, and validation to a leased
`worker` or method worker. It handles Git/PR and non-code work, then reads only the complete final
diff, key excerpts, and validation output for acceptance. Independent Review still follows current
risk and the PR/merge triggers of `codex-review-gate`. Failed agents require re-decomposition,
replacement, or a blocker report; after three unsuccessful Worker rounds, only read-only
re-decomposition or a blocker report is allowed. No fourth code-writing round starts, and new code
writes wait for a new user direction or explicit mode exit.

This project installs no Hook. Agent profiles own derived-agent identity and read-only scope;
`codex-orchestration` owns root-task Agent execution, while `codex-review-gate` defines the
PR Review and final merge-check route and Reviewer authorization. The review-owning root executes
classification, authorized remediation, and verification; the merge-owning root owns integration; main-agent acceptance still checks the
complete worker diff and validation. Delegation uses compact natural-language briefs instead of
fixed authorization fields.

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
keep global context small. The Review pointer requires `codex-review-gate` after creating or updating a PR, when asked to
review an existing PR including external contributions, and before an authorized primary-branch merge.
Ordinary local completion, branch-only handoff without a review request, and repositories without
Git history do not trigger it. PR creation/update includes Review but not merge authorization.
The gate authorizes only its R1-R3 read-only Reviewers. Ordinary proactive-delegation admission
cannot suppress those Reviewer calls, while implementation and investigation delegation retain
their normal threshold. Loading the gate classifies the latest candidate diff; it does not by
itself start a Reviewer, since R0 completes with main-agent validation only.

## PR Review and final merge check

Review needs committed source and target histories and a pinned candidate diff; inability to pin it blocks the merge until the required history and refs are available. Start Review independently
of CI availability and alongside relevant CI when configured. Use appropriate local validation
when CI is absent; disclose validation gaps. Expected CI awaiting approval, missing a run, or
failing to start is a blocker, not absent CI or a pass. Do not create CI merely for this gate.
External contributions follow the same risk criteria, with no implicit authority to edit the
contributor's branch, approve workflow execution, or merge.

R0 covers local,
self-contained changes that the main agent completely verified at the boundary where their behavior
is observable, that are easy to recover, and that leave no material failure hypothesis current
validation does not exclude; runtime behavior changes qualify, and a self-contained illustrative or
demonstration artifact is a typical example. R1 covers one localized, validated, recoverable
material failure hypothesis that independent judgment could change, including localized runtime,
public-contract, managed-policy, test-semantic, dependency, or build changes; R2 covers multiple
independent risks, broad or hard-to-recover public contracts, sensitive boundaries, or material
uncertainty; R3 covers changed trust or authorization boundaries and high-impact failure. The
highest matching level wins, diff size alone never decides the level, and material uncertainty
fails closed to the higher level or R2 fallback.

The risk level does not set a Reviewer quota. R1-R3 always select at least one matching read-only
Reviewer; extra seats require additional material hypotheses where independent judgment can change
integration, and R3 still ends with adversarial verification. Validation-proven properties and missing
evidence axes do not receive filler Reviewers.

R1 uses `correctness-reviewer` as its general default. When its sole material hypothesis clearly
belongs to architecture, security, performance, test reliability, or another specialist domain,
the matching specialist replaces the default rather than adding a second Reviewer.

R0 uses main-agent inspection and validation only. R1-R3 use the Reviewer coverage selected above,
and R3 performs focused Review and root-controlled remediation before an `adversarial-verifier`.
Review Agent execution reuses `codex-orchestration`; the Review Skill does not duplicate model
routing, lifecycle, or waiting policy.

Each normal Reviewer stays within its assigned change boundary and risk. When a finding depends on
a task or spec requirement or a repository standard, the Reviewer cites that source and identifies
the evidence class without starting a generic Standards/Spec pass. Labelled judgment calls remain
distinct, and Reviewers omit checks conclusively covered by current passing tooling unless the
tool's coverage or evidence is itself part of the assigned risk.

The review-owning root decides findings and controls authorized remediation and validation; the
merge-owning root retains final integration authority. In ordinary mode, the main agent may implement an accepted fix and rerun affected
validation. In manager-only mode, the leased worker implements the accepted fix and runs validation;
the root inspects and accepts that result before the original Reviewer receives a same-thread
targeted follow-up against the candidate diff. This closes the assigned finding without restarting a
full Review merely to obtain a clean report.
Before merge, reuse Review whose candidate boundary, coverage, findings, and validation evidence
remain applicable. Changes to the head or target/base require inspection of the changed diff and
integration effects, reclassification where needed, and only affected supplemental checks.
Repeat a full Review only when earlier conclusions cannot be preserved. A prior approval alone
does not establish coverage. Optional early consultation can contribute evidence for the risks it covers.

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
exists, ordinary mode lets the main agent take over, decompose again, or report the blocker.
Manager-only mode follows `references/manager-only.md`: it may only re-decompose read-only or report
a blocker at that boundary, never start a fourth code-writing round, and waits for a new user
direction or explicit mode exit before new code-writing work.

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
