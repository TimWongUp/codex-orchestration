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
- `<codex-home>/hooks/orchestration_route.py` and `<codex-home>/hooks/subagent_scope.py` — only
  when Hooks are approved.
- `<codex-home>/hooks.json` — merged only when Hooks are approved.
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

## Retired v1 lifecycle assets

Pure v2 retirement is required even when the user declines the current optional Hooks. The
installing Agent inspects the managed Hook directory and Hook configuration, shows any former
`subagent_guard.py` file, v1-shaped Guard registration, known prior v1
`orchestration_route.py`, or its `UserPromptSubmit` registration in the installation plan. It
changes only approved assets whose prior project ownership is confirmed. The Hook directory must
be physical, and known prior copies are recognized with LF or CRLF line endings.

Known legacy event/matcher pairs plus an exact two-argument Python command identify a Guard
registration candidate even when it points to an older Codex home, checkout, or Python executable.
A Route registration is confirmed only when its exact Python command points to the confirmed legacy
Route projection. If current Hooks are approved, the installer replaces that projection with the
current v2 source and retains one effective registration; otherwise it removes the confirmed legacy
file and registration. Ambiguous, external, linked, or different same-named assets remain conflicts,
not automatic deletion targets, and unresolved v1-shaped conflicts block a pure v2 completion
claim. If cleanup or the required Route update is declined, the installation remains mixed v1/v2.

## V2 collaboration tools

The optional Hooks add only routing and derived-agent identity reminders. The lifecycle contract is
owned by the Skill: `spawn_agent` creates an agent (ordinary calls use `fork_turns="none"`),
`send_message` queues supplemental context without starting a turn, `followup_task` delivers
genuine later or corrective work to a running target at its next boundary and starts a new turn for
an idle non-root target, `wait_agent` waits for the caller mailbox, `interrupt_agent`
interrupts an active turn while preserving context, and `list_agents` plus final notifications
reconcile the current tree. There is no cross-call delivery envelope or cached lifecycle result. A third worker
round creates a fresh agent instead of closing an old thread.

Each lifecycle call is a separate model-visible operation. Hosts with direct tools use them; when
only `functions.exec` exposes those tools, each program makes one lifecycle call, returns the
structured result unchanged, and leaves the next lifecycle decision to the model.

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
placeholders with values available on the current host, and review the full order before approving
the Agent's write.

Optional `task_overrides` entries prepend one local model and reasoning-effort configuration for a
clearly named task kind and a bounded list of roles. Explicit user choices still win; unmatched
tasks use the ordinary role route, and unavailable override models fall back to that role's first
available entry. Worker retries and model-diverse panels continue through this combined effective
route rather than treating the override as a permanent pin.

Without a local route file, omitting model selection requests inheritance from the current Codex
configuration; it does not confirm the resolved model.

## Verification

```text
python scripts/validate.py
python scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root>
python scripts/validate.py --runtime --hooks --codex-home <codex-home> --skills-root <skills-root>
```

Use the interpreter command available on the host. `--skills-root` is required so validation
cannot guess a non-active location. Runtime validation checks exact bundled Skill and Agent copies,
validates any saved task-package language, rejects linked managed targets, and rejects retired v1
guard files or registrations. Add `--hooks` only when current Hooks were approved; it then checks
the exact scripts, parses `hooks.json`, and requires one effective registration per managed event.
The installing Agent separately verifies any approved model route.
