# Configuration

## Authority boundary

Portable orchestration behavior is edited and reviewed in this repository. Installed Skill,
Agent, and Hook files are deployment artifacts and should not be edited directly. Host-specific
task-package language, model routes, and Hook registrations remain outside Git so one repository
can serve different machines without publishing private paths or model identifiers.

## Install scope

The user's Agent resolves the active paths before installation by inspecting the current runtime,
configuration, installed Skill listings, and current official locations. It does not assume one
generic Skill root. Managed destinations are:

- `<skills-root>/codex-orchestration` — the main Skill copy.
- `<skills-root>/diagnosing-bugs` — the bundled complete debugging Skill copy.
- `<skills-root>/prototype` — the bundled complete prototype Skill copy.
- `<codex-home>/agents/*.toml` — managed custom-agent copies.
- `<codex-home>/hooks/subagent_scope.py` — only when the writer-lease Hook is approved.
- `<codex-home>/hooks.json` — merged only when the Hook is approved.
- `<codex-home>/codex-orchestration/preferences.toml` — only when a task-package language is
  saved.
- `<codex-home>/codex-orchestration/model-routing.toml` — only when local routing is approved.

`INSTALL.md` is the authority for path discovery, planning, conflict handling, optional choices,
and verification. Installation creates copies rather than links so the same contract works on
macOS and native Windows. Existing symlinks and non-directory parents are conflicts: the Agent
does not traverse, unlink, replace, or write through them. Unrelated files and Hook registrations
are preserved.

Externally owned registrations and deployment metadata are reported with their owning runtime or
registry and left untouched. They are outside the `current`, `missing`, `drift`, and `conflict`
states used for managed installation targets.

## Existing Skill preflight

All three Skill targets are checked before any installation write:

- An exact source copy is `current`.
- A missing Skill is planned for creation.
- A same-named but different Skill, a symlink, a non-directory Skill target, or a non-directory
  parent is a conflict and remains untouched.

Managed Agent, Hook, preference, and routing targets are classified the same way. Differing
managed files are drift. The Agent shows the difference and replaces it only after explicit
approval; conflicts are left for the user to resolve without deletion.

Those rules govern ordinary installation. During a one-time migration from another source,
`INSTALL.md` section 7 is authoritative: after the user approves the exact cutover targets, the
Agent may remove only the confirmed managed links before installing the physical runtime
projection. Old source directories are still retained unless the user separately approves their
retirement.

## Retired lifecycle and Route assets

Pure v2 retirement is required even when the user declines the current optional Hook. The
installing Agent inspects the managed Hook directory and Hook configuration, shows any former
`subagent_guard.py` file, v1-shaped Guard registration, known prior project
`orchestration_route.py`, or its `UserPromptSubmit` registration in the installation plan. It
changes only approved assets whose prior project ownership is confirmed. The Hook directory must
be physical, and known prior copies are recognized with LF or CRLF line endings.

Known legacy event/matcher pairs plus an exact two-argument Python command identify a Guard
registration candidate even when it points to an older Codex home, checkout, or Python executable.
A Route registration is confirmed only when its exact Python command points to the confirmed prior
Route projection. The installer removes confirmed v1 and v2 project Route copies and registrations.
Ambiguous, external, linked, or different same-named assets remain conflicts, not automatic
deletion targets, and unresolved project-shaped conflicts block a pure v2 completion claim. If
cleanup is declined, the installation remains mixed v1/v2.

## V2 collaboration boundary

The model-visible collaboration-tool schemas own call mechanics. This repository does not wrap
those tools, cache their return shapes, or define a transport fallback. The Skill adds only
orchestration policy: ordinary delegation uses `fork_turns="none"`, pending results form a
dependency barrier, a follow-up invalidates earlier completion evidence, an explicit stop converges
the active tree, and a third worker round starts with a fresh package and lease.

The optional Hook reinforces only the writable-worker lease check. Agent profiles own derived-agent
identity and read-only scope; no project `UserPromptSubmit` Hook restates main-agent policy.

## Task-package language

An explicit language request wins. Otherwise the main Skill reads
`<codex-home>/codex-orchestration/preferences.toml` when present. Supported persisted values are
`en` and `zh-CN`; without the file, task-package prose follows the current user's language.

The preference changes natural-language descriptions and the requested return language only.
Canonical field names such as `GOAL`, `SCOPE`, and `RETURN`, plus fixed lease and control literals,
remain unchanged. Installation starts from `examples/preferences.toml`, shows the selected file,
and preserves an existing valid preference unless the user approves a change.

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

`panel_routes.gpt` and `panel_routes.third_party` are used only by `panel` and
`WORKSTREAM: panel` in `hybrid`; every Hybrid task also declares `WORKSTREAM: panel | specialist`.
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
python scripts/validate.py --runtime --hooks --codex-home <codex-home> --skills-root <skills-root>
```

Use the interpreter command available on the host. `--skills-root` is required so validation
cannot guess a non-active location. Runtime validation checks exact bundled Skill and Agent copies,
validates any saved task-package language and model route, rejects linked managed targets, and
rejects retired Guard or Route files and registrations. Add `--hooks` only when the current Hook
was approved; it then checks the exact script, parses `hooks.json`, and requires one effective
`SubagentStart` registration. The installing Agent separately verifies that the host can enforce
each approved model route entry.
