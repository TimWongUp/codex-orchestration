# Agent installation contract

Use this contract when the user asks to install, update, repair, or verify this checkout for
their local Codex environment. Read it completely before changing user configuration.

This checkout is the source of truth for portable Skill, Agent, and the three orchestration Hooks
named in section 4. Shared context, memory-routing, and closeout Hooks remain owned by their source
runtime. Installed copies are runtime artifacts and are never edited as an alternate source. Model
routes, task-package language, Hook registrations, executable paths, and unrelated user
configuration remain local.

## 1. Preflight

1. Using the Python interpreter command available on the host, confirm the checkout passes
   `scripts/validate.py`.
2. Detect the host platform, the active Codex home, and the Skill root that this Codex runtime
   actually loads. Inspect current configuration and installed Skill listings; check both
   `<codex-home>/skills` and current official user or repository Skill locations when relevant.
   Do not infer the active root from a generic default. Record the exact selected paths in the
   plan.
3. Inspect every source and destination named below before writing. Classify each managed target as
   `current`, `missing`, `drift`, or `conflict`. External ownership is recorded separately and is
   not a managed target classification; report the owning runtime or deployment registry and leave
   its files or registrations outside this contract untouched.
4. Show one complete installation plan. Required components may be applied after the user
   approves that plan. On first install or when no valid preference exists, ask whether task-package
   prose should use English or Simplified Chinese. Ask separately about Hooks and model routing
   because both are optional.

Preflight is complete only when every destination has a classification and the user can see
every proposed create or replacement.

## 2. Required components

Install copies rather than creating new links so the same contract works on macOS and native
Windows. Existing links are conflicts and are never traversed or replaced by this procedure.

| Source | Destination |
| --- | --- |
| `SKILL.md` and `references/` | `<skills-root>/codex-orchestration/` |
| `skills/diagnosing-bugs/` | `<skills-root>/diagnosing-bugs/` |
| `skills/prototype/` | `<skills-root>/prototype/` |
| `agents/*.toml` | `<codex-home>/agents/` |

A required destination is current only when every source file named by this contract is an exact
copy. A same-named but different Skill, a symlink, or a non-directory Skill target is a conflict.
Differing managed Agent files are drift only when their parent and target are physical paths;
linked targets are conflicts.

Create a parent only when it is absent and its nearest existing ancestor is a physical directory.
If a destination or any existing parent below the selected root is a symlink, file where a
directory is required, or other non-directory path, classify it as a conflict and perform no
write through it. Preserve unrelated Skills, Agents, configuration, and files. Replace drift
only after showing the difference and receiving explicit approval. A conflict is resolved by the
user choosing a different target or explicitly moving the existing path; the installation does
not delete, unlink, follow, or replace it.

Do not register the checkout root itself as one Skill or copy the whole repository into
`<skills-root>/codex-orchestration`. The main Skill is only the `SKILL.md` plus `references/`
projection shown above; the bundled method Skills, Agents, and optional Hooks have distinct
destinations. A separate deployment registry may point to this checkout as its content authority,
but it must mark the suite as externally installed and defer all runtime writes to this contract.

## 3. Task-package language

Task-package field names and fixed control literals stay in their canonical English form. The
natural-language descriptions and requested return language may use English or Simplified Chinese.

On first install, or when `<codex-home>/codex-orchestration/preferences.toml` is missing, ask the
user to choose English (`en`) or Simplified Chinese (`zh-CN`). If the user approves persistence,
start from `examples/preferences.toml`, replace `LANGUAGE` with the selected value, show the exact
file, and write it to that destination. If the user declines persistence, leave the file absent;
the Skill then follows the current user's language. Preserve an existing valid preference unless
the user explicitly asks to change it, and never replace a different or invalid file without
showing the difference and receiving approval.

An explicit language request in the current task overrides the saved preference.

## 4. Optional Hooks

Ask whether the user wants the orchestration Hooks. If approved:

1. Copy `hooks/orchestration_route.py`, `hooks/subagent_scope.py`, and
   `hooks/subagent_guard.py` to `<codex-home>/hooks/` under the same drift rules as required files.
2. Read `<codex-home>/hooks.json`, or start from an empty object when it is absent.
3. Merge the managed command Hooks while preserving unrelated top-level keys, event groups,
   matchers, commands, shared-runtime Hooks, and ordering where practical. Register `orchestration_route.py` for
   `UserPromptSubmit`, `subagent_scope.py` for `SubagentStart`, and `subagent_guard.py` for
   `PreToolUse` with matcher `send_input$` plus `PostToolUse` with matcher `wait_agent$`. The
   PostToolUse registration adds a stateless advisory when the host surfaces a direct non-terminal
   wait result. It does not inspect outer `functions.exec` results. Do not register this guard for
   `close_agent`; upgrades must remove old close or combined managed registrations while
   preserving unrelated registrations.
   The guard does not enforce close ordering. Codex flattens namespaced local function names by concatenating the namespace and
   function name, so the suffix matcher covers both flattened and unnamespaced forms.
4. Resolve the current Python executable to an absolute path. The effective command contains
   exactly two arguments: that executable and the managed script's absolute path. On macOS write
   the correctly quoted POSIX `command`. On Windows write both `command` and `commandWindows` as
   the same canonical Windows-quoted command string with JSON-escaped paths. After JSON parsing,
   the two fields must be byte-for-byte identical and contain the same exact two arguments. Do not
   add shell wrappers, extra arguments, suffixes, or duplicate commands.
5. Parse the final JSON and show the exact added or changed Hook groups before writing it.

Hook installation is complete only when all three scripts match the checkout, each event has one
effective managed registration with the exact managed matcher, and no registration invokes this
suite's guard for `close_agent`, outer `functions.exec`, or an old combined matcher. Shared context,
memory-routing, and closeout registrations remain owned by their source runtime and are outside
this contract.

## 5. Optional model routing

Ask separately whether the user wants local model routing. Without it, omitting model selection
only requests inheritance from the current Codex settings; it does not confirm the resolved model.

If approved, start from `examples/model-routing.toml`, replace every placeholder only with
models and reasoning levels available on the current host, remove unused example entries, show
the complete task overrides and route order, and write the approved file to
`<codex-home>/codex-orchestration/model-routing.toml`. Preserve an existing route unless the user
explicitly approves its replacement. Never copy another user's model identifiers or change
unrelated Codex defaults.

## 6. One-time migration from another source

When an existing installation is a link or copy from a personal checkout, Vault, or other source,
preflight first records its resolved source and the complete differences from this checkout. Keep
the local task-package preference, local model routing, and unrelated Hook registrations; do not
import private Agent or Hook behavior as repository source.

The existing path remains a conflict until the user explicitly approves the exact cutover targets.
After that approval, remove only the confirmed managed links or move conflicting physical paths to
a user-approved location, install the required physical copies from the source projection in
section 2, then apply any separately approved Hook update from section 4. Never replace the main
Skill alone while leaving bundled method Skills, Agent profiles, or approved Hook scripts sourced
from the old implementation.

Run the full verification below before retiring the old source directory. Deleting or archiving
that old source is a separate user decision; a successful runtime cutover does not imply it.

## 7. Verification

Run:

```text
python scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root>
```

Use the interpreter command available on the host. Runtime validation checks any saved
task-package language. Add `--hooks` only when Hooks were approved; without that flag, existing Hook
scripts and registrations are outside verification scope. Then verify any approved model route
directly, report every remaining drifted or skipped component, and tell the user to start a new
Codex task so custom Skills and Agents reload.

Installation is complete only when source validation passes, required runtime files validate,
optional components match the user's choices, any saved task-package language is exactly `en` or
`zh-CN`, and no unapproved target was replaced.
