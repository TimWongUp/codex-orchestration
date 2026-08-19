# Agent installation contract

Use this contract when the user asks to install, update, repair, or verify this checkout for
their local Codex environment. Read it completely before changing user configuration.

## 1. Preflight

1. Using the Python interpreter command available on the host, confirm the checkout passes
   `scripts/validate.py`.
2. Detect the host platform, the active Codex home, and the Skill root that this Codex runtime
   actually loads. Inspect current configuration and installed Skill listings; check both
   `<codex-home>/skills` and current official user or repository Skill locations when relevant.
   Do not infer the active root from a generic default. Record the exact selected paths in the
   plan.
3. Inspect every source and destination named below before writing. Classify each target as
   `current`, `missing`, `external`, `drift`, or `conflict`.
4. Show one complete installation plan. Required components may be applied after the user
   approves that plan. Ask separately about Hooks and model routing because both are optional.

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

## 3. Optional Hooks

Ask whether the user wants the orchestration Hooks. If approved:

1. Copy `hooks/orchestration_route.py`, `hooks/subagent_scope.py`, and
   `hooks/subagent_guard.py` to `<codex-home>/hooks/` under the same drift rules as required files.
2. Read `<codex-home>/hooks.json`, or start from an empty object when it is absent.
3. Merge the managed command Hooks while preserving unrelated top-level keys, event groups,
   matchers, commands, and ordering where practical. Register `orchestration_route.py` for
   `UserPromptSubmit`, `subagent_scope.py` for `SubagentStart`, and `subagent_guard.py` for both
   `PreToolUse` with matcher `send_input$|close_agent$` and `PostToolUse` with matcher
   `wait_agent$`. Codex flattens namespaced local functions by concatenating the namespace and
   function name, so the suffix matcher covers both flattened and unnamespaced forms.
4. Resolve the current Python executable to an absolute path. The effective command contains
   exactly two arguments: that executable and the managed script's absolute path. On macOS write
   the correctly quoted POSIX `command`. On Windows write a valid `command` plus the canonical
   Windows `commandWindows` override, with JSON-escaped paths. Do not add shell wrappers, extra
   arguments, suffixes, or duplicate commands.
5. Parse the final JSON and show the exact added or changed Hook groups before writing it.

Hook installation is complete only when all three scripts match the checkout and each event has
one effective managed registration with the exact managed matcher.

## 4. Optional model routing

Ask separately whether the user wants local model routing. Without it, the orchestration Skill
inherits the current Codex model settings.

If approved, start from `examples/model-routing.toml`, replace every placeholder only with
models and reasoning levels available on the current host, show the complete route order, and
write the approved file to `<codex-home>/codex-orchestration/model-routing.toml`. Preserve an
existing route unless the user explicitly approves its replacement. Never copy another user's
model identifiers or change unrelated Codex defaults.

## 5. Verification

Run:

```text
python scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root>
```

Use the interpreter command available on the host. Add `--hooks` only when Hooks were approved;
without that flag, existing Hook scripts and registrations are outside verification scope. Then
verify any approved model route directly, report every remaining drifted or skipped component,
and tell the user to start a new Codex task so custom Skills and Agents reload.

Installation is complete only when source validation passes, required runtime files validate,
optional components match the user's choices, and no unapproved target was replaced.
