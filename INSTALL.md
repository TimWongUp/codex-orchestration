# Deterministic installation contract

Use this contract when installing, updating, repairing, or verifying this checkout for a local
Codex environment. Read it completely before changing user configuration.

`scripts/install.py` is the only write implementation of this contract. It plans by default and
writes only with `--apply`. Do not reproduce its projection with ad hoc copy commands. The checkout
remains the source of truth for portable Skills, Agents, the managed global-rules block, and the
writer-lease Hook. Installed files are runtime artifacts; task-package language, model routes,
executable paths, Hook trust, and unrelated user configuration stay local.

## 1. Choose the runtime targets

Use the Python interpreter available on the host (`python3`, `py -3`, or `python`). Python 3.9 or
newer is required.

Resolve these paths before running the installer:

- `--codex-home`: the active Codex home. An explicit value wins, then `CODEX_HOME`, then the
  documented Codex default `~/.codex`.
- `--skills-root`: the Skill root loaded by the current Codex runtime. This argument is required so
  the installer never guesses a non-default active root.

Inspect current Codex configuration and installed Skill listings when the active Skill root is not
already known. Existing deployment registries may record this checkout as the suite authority, but
they must mark its members as externally installed and leave runtime writes to this installer.

## 2. Plan before applying

On macOS, a typical Simplified Chinese setup with the optional Hook is:

```text
python3 scripts/install.py --codex-home ~/.codex --skills-root ~/.agents/skills --language zh-CN --hooks
```

On native Windows PowerShell:

```text
py -3 scripts/install.py --codex-home "$HOME\.codex" --skills-root "$HOME\.agents\skills" --language zh-CN --hooks
```

The first command is always a dry run. It validates the checkout, classifies every managed target,
prints every proposed create, update, or authenticated retirement, shows the exact global-rules
block and managed Hook group, and reports conflicts without writing.

Review that output, then repeat the same command with `--apply`. When an Agent performs the
installation, it shows the dry-run plan and obtains approval before adding `--apply`.

The first install requires `--language en` or `--language zh-CN`. A later run preserves an existing
valid choice when `--language` is omitted; passing a different value explicitly plans that change.

## 3. Required runtime projection

The installer copies physical files so the same result works on macOS and native Windows:

| Source | Destination |
| --- | --- |
| `SKILL.md` and `references/` | `<skills-root>/codex-orchestration/` |
| `skills/diagnosing-bugs/` | `<skills-root>/diagnosing-bugs/` |
| `skills/prototype/` | `<skills-root>/prototype/` |
| `agents/*.toml` | `<codex-home>/agents/` |
| rendered `examples/preferences.toml` | `<codex-home>/codex-orchestration/preferences.toml` |

Do not register the repository root as one Skill or flatten bundled method Skills into the main
Skill. The runtime is a component projection.

A target is `current` when its bytes match, `missing` when it can be created safely, and `drift`
when a physical managed file needs replacement. A same-named Skill whose frontmatter identifies a
different Skill is a conflict. A non-empty Skill directory without a physical `SKILL.md`, a linked
target, or a file where a directory is required is also a conflict.

Every existing parent below the selected roots must be a physical directory. User-created
symlinks, Windows reparse points such as junctions, and paths containing `..` are conflicts. The
platform-owned `/var`, `/tmp`, and `/etc` aliases on macOS are canonicalized before the displayed
plan. Managed targets at or beyond the conservative native Windows path limit are conflicts rather
than partial long-path support. The installer never intentionally traverses, unlinks, or replaces links. It preserves
unrelated Skills, Agents, local preferences, model routes, configuration keys, and files. New
POSIX directories use mode `0700`; replacement preserves an existing POSIX file mode or Windows
file ACL and attributes.

## 4. Managed global rules

Global orchestration rules are enabled by default. The canonical block lives in
`examples/global-agents-block.md` and is deliberately small: it points the main agent to the Skill
and keeps the full workflow out of always-loaded context.

Codex loads the first non-empty global instruction file in this order:

1. `<codex-home>/AGENTS.override.md`
2. `<codex-home>/AGENTS.md`

The installer applies the same rule without following links. It owns only the exact block between
`CODEX-ORCHESTRATION:GLOBAL-RULES` markers. Content outside that block is retained byte-for-byte,
including its line endings. Re-running setup replaces one complete owned block in place. If the
active global file changes, setup removes the owned block from the inactive file and injects it
into the active file so only one copy remains.

Missing markers create a new block. Nested, unmatched, or duplicated markers are conflicts and
block the complete transaction. Any marker token outside an exact standalone marker line is also
malformed and conflicts. Use `--no-global-rules` to leave both global instruction files unchanged;
that option does not uninstall an existing block.

## 5. Optional writer-lease Hook

Pass `--hooks` to install the Hook. Without it, the current writer-lease script and registration are
left unchanged.

When selected, setup:

1. Copies `hooks/subagent_scope.py` to `<codex-home>/hooks/subagent_scope.py`.
2. Reads `<codex-home>/hooks.json`, or starts a new object when the file is absent.
3. Removes current registrations only when an exact two-argument Python command invokes that
   managed target, then appends one `SubagentStart` group.
4. Preserves unrelated top-level fields, events, matcher groups, handlers, and order.
5. Uses the absolute current Python executable and managed script path. On Windows, `command` and
   `commandWindows` contain the same canonical Windows-quoted two-argument command.

An existing object without a `hooks` field is treated as an empty Hook map; a non-object `hooks`
value is a conflict. UTF-8 JSON with or without a byte-order mark is accepted. Duplicate keys and
non-standard constants are conflicts. On Windows, executable or managed-script paths containing
`%`, `!`, a double quote, or a newline are rejected because `cmd.exe` can reinterpret them.

Codex treats user Hooks as non-managed code. After installation, start a new task, open `/hooks`,
review the exact definition, and trust it before expecting it to run. A changed Hook hash requires
review again.

The Hook reinforces only the writable-worker lease check. It does not grant a lease, narrow the
sandbox, replace the task package, or implement main-agent routing. Shared context, memory-routing,
and closeout Hooks remain owned by their source runtime.

## 6. Retired project Hook assets

Pure v2 verification rejects the former `subagent_guard.py` and project
`orchestration_route.py` assets even when `--hooks` is not selected.

The installer removes a retired file only when its bytes match a known prior project hash. It
removes a former registration only when the handler is an exact two-argument Python command, has a
known legacy event/matcher shape, and its referenced script has authenticated prior-project bytes.
An exact reference to the managed retired target outside those known shapes blocks retirement so
setup cannot create a dangling custom registration. Project-shaped Hook command paths containing
`..`, relative syntax, or shell expansion characters are unsafe and conflict instead of being
normalized through an unchecked parent. Existing filesystem aliases are compared by file identity;
macOS case aliases are conservatively case-folded even after the target disappears. Every existing
physical script referenced by a recognized Python invocation or explicit command path is also
checked against known retired hashes, so environment wrappers, renamed hardlinks, and nested
commands cannot retain retired project code. Ambiguous, missing, linked, or
different same-named assets remain conflicts. Unrelated Hook text that merely mentions a retired
filename is preserved.

Declining or failing authenticated retirement blocks a pure v2 completion claim. Old source
directories outside Codex home remain untouched; deleting or archiving them is a separate user
decision.

## 7. Local model routing

Setup does not create or change `<codex-home>/codex-orchestration/model-routing.toml`. Available
models, reasoning levels, and service-tier enforcement are host facts that must be verified live.

When local routing is wanted, start from `examples/model-routing.toml`, replace every placeholder
with supported host values, remove unused examples, review the complete file, and install it only
after explicit approval. An existing route remains local and is preserved by setup. Omitting model
selection requests inheritance from current Codex settings; it does not confirm the resolved model.

## 8. Transaction and conflicts

Within one running installer process, a caught write or verification failure triggers rollback of
the displayed managed file operations:

- Each write uses a same-directory temporary file and atomic replacement.
- The installer retains the pre-transaction bytes in memory.
- A caught write failure or failed post-install verification restores completed target bytes and
  removes newly created empty directories where possible.
- A preflight conflict prevents all writes.

The plan is a snapshot, not a lock. Before each operation, the installer rechecks the physical
path and the target bytes captured during planning, and it rechecks the result after each operation.
A target that appears, disappears, changes, or gains a linked parent blocks the transaction. This
is not an operating-system security boundary against an adversarial same-user process; do not edit
or replace the selected runtime roots concurrently.

An abrupt process termination or power loss is not journaled and can leave a partial projection or
a same-directory installer temporary file. After either event, stop concurrent editors, run a fresh
dry run, inspect every reported drift or conflict, and apply again only after the plan is understood.
Rollback restores managed bytes; metadata for a retired file recreated after deletion can inherit
the destination defaults.

A one-time migration from links or a different checkout remains an explicit cutover. The installer
reports those paths as conflicts; the user first chooses the exact targets to move or unlink, then
runs a new dry run. Successful installation never implies permission to remove the old source.

## 9. Verification

`--apply` automatically runs source validation and the selected runtime checks. The equivalent
manual command for a setup with global rules and Hook is:

```text
python3 scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root> --global-rules --hooks
```

Without the optional Hook, omit `--hooks`. With `--no-global-rules`, omit `--global-rules`.

Installation is complete only when required Skill and Agent copies match, any saved language or
model route is valid, selected optional components match, no retired project Hook remains, and no
unapproved target was changed. Start a new Codex task after success so Skills, Agents, global rules,
and Hooks reload.
