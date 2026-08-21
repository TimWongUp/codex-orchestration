# Configuration

## Authority boundary

Portable orchestration behavior is edited and reviewed in this repository. Installed Skill,
Agent, and Hook files are deployment artifacts and should not be edited directly. Host-specific
task-package language, model routes, and Hook registrations remain outside Git so one repository
can serve different machines without publishing private paths or model identifiers.

## Install scope

The user's Agent resolves the active paths before installation by inspecting the current runtime, configuration, installed Skill listings, and current official locations. It does not assume one generic Skill root. Managed destinations are:

- `<skills-root>/codex-orchestration` — the main Skill copy.
- `<skills-root>/diagnosing-bugs` — the bundled complete debugging Skill copy.
- `<skills-root>/prototype` — the bundled complete prototype Skill copy.
- `<codex-home>/agents/*.toml` — managed custom-agent copies.
- `<codex-home>/hooks/orchestration_route.py`, `<codex-home>/hooks/subagent_scope.py`, and
  `<codex-home>/hooks/subagent_guard.py` — only when Hooks are approved.
- `<codex-home>/hooks.json` — merged only when Hooks are approved.
- `<codex-home>/codex-orchestration/preferences.toml` — only when a task-package language is saved.
- `<codex-home>/codex-orchestration/model-routing.toml` — only when local routing is approved.

`INSTALL.md` is the authority for path discovery, planning, conflict handling, optional choices, and verification. Installation creates copies rather than links so the same contract works on macOS and native Windows. Existing symlinks and non-directory parents are conflicts: the Agent does not traverse, unlink, replace, or write through them. Unrelated files and Hook registrations are preserved.

## Existing Skill preflight

All three Skill targets are checked before any installation write:

- An exact source copy is `current`.
- A missing Skill is planned for creation.
- A same-named but different Skill, a symlink, a non-directory Skill target, or a non-directory parent is a conflict and remains untouched.

Managed Agent, Hook, preference, and routing targets are classified the same way. Differing managed files are drift. The Agent shows the difference and replaces it only after explicit approval; conflicts are left for the user to resolve without deletion.

Those rules govern ordinary installation. During a one-time migration from another source,
`INSTALL.md` section 6 is authoritative: after the user approves the exact cutover targets, the
Agent may remove only the confirmed managed links before installing the physical runtime
projection. Old source directories are still retained unless the user separately approves their
retirement.

The optional guard stores only hashed session and agent identifiers as terminal marker filenames
under the platform temporary directory. `wait_agent` timeouts do not create markers. Delete the
temporary `codex-orchestration-subagents` directory only when no Codex session is using it.

Preflight is complete only after every destination is classified and one complete plan has been shown. Task-package language, Hooks, and model routing are separate local decisions.

## Task-package language

An explicit language request wins. Otherwise the main Skill reads
`<codex-home>/codex-orchestration/preferences.toml` when present. Supported persisted values are
`en` and `zh-CN`; without the file, task-package prose follows the current user's language.

The preference changes natural-language descriptions and the requested return language only.
Canonical field names such as `GOAL`, `SCOPE`, and `RETURN`, plus fixed lease and control literals,
remain unchanged. Installation starts from `examples/preferences.toml`, shows the selected file,
and preserves an existing valid preference unless the user approves a change.

## Model routes

The repository does not ship active routes. Start from `examples/model-routing.toml`, replace placeholders with values available on the current host, and review the full order before approving the Agent's write.

Optional `task_overrides` entries prepend one local model configuration for a clearly named task kind and a bounded list of roles. Explicit user choices still win; unmatched tasks use the ordinary role route, and unavailable override models fall back to that role's first available entry. Worker retries and model-diverse panels continue through this combined effective route rather than treating the override as a permanent pin.

Without a local route file, the main agent inherits the current Codex model configuration.

## Verification

```text
python scripts/validate.py
python scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root>
python scripts/validate.py --runtime --hooks --codex-home <codex-home> --skills-root <skills-root>
```

Use the interpreter command available on the host. `--skills-root` is required so validation cannot guess a non-active location. Runtime validation checks exact bundled Skill and Agent copies, validates any saved task-package language, and rejects linked managed targets. Add `--hooks` only when Hooks were approved; it then checks the exact scripts, parses `hooks.json`, and requires one effective registration per managed event. The installing Agent separately verifies any approved model route.
