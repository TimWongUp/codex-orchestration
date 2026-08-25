# Deterministic installation contract

Use this contract when installing, updating, repairing, or verifying this checkout for a local
Codex environment. Read it completely before changing user configuration.

`scripts/install.py` is the only write implementation of this contract. It plans by default and
writes only with `--apply`. Do not reproduce its projection with ad hoc copy commands. The checkout
remains the source of truth for portable Skills, Agents, the managed global-rules block, and the
deterministic installer. Installed files are runtime artifacts; task-package language, model
routes, unrelated Hook registrations, and unrelated user configuration stay local.

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

On macOS, a typical Simplified Chinese setup is:

```text
python3 scripts/install.py --codex-home ~/.codex --skills-root ~/.agents/skills --language zh-CN
```

On native Windows PowerShell:

```text
py -3 scripts/install.py --codex-home "$HOME\.codex" --skills-root "$HOME\.agents\skills" --language zh-CN
```

The first command is always a dry run. It validates the checkout, classifies every managed target,
prints every proposed create, update, or authenticated retirement, shows the exact global-rules
block, and reports conflicts without writing.

Review that output, then repeat the same command with `--apply`. When an Agent performs the
installation, it shows the dry-run plan and obtains approval before adding `--apply`.

The first install requires `--language en` or `--language zh-CN`. A later run preserves an existing
valid choice when `--language` is omitted; passing a different value explicitly plans that change.

## 3. Required runtime projection

The installer copies physical files so the same result works on macOS and native Windows:

| Source | Destination |
| --- | --- |
| `SKILL.md` and `references/` | `<skills-root>/codex-orchestration/` |
| `skills/codex-review-gate/` | `<skills-root>/codex-review-gate/` |
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
unrelated Skills, Agents, local preferences, model routes, configuration keys, and files. A retired
project Agent is removed only when its bytes match a known prior project version; a different
same-named file is an ownership conflict. New
POSIX directories use mode `0700`; replacement preserves an existing POSIX file mode or Windows
file ACL and attributes.

## 4. Managed global rules

Global orchestration and code Review rules are enabled by default. The canonical block lives in
`examples/global-agents-block.md` and is deliberately small: it points the main agent to the two
policy Skills and keeps their full workflows out of always-loaded context.

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
that option does not uninstall an existing block. It permits no managed block as an explicit
opt-out, but an owned block that already exists must match the current canonical block. A stale or
malformed owned block conflicts so an update cannot silently install new Skills with old Review
routing.

## 5. No project Hook installation

This project installs no Hook. Worker authority, task boundaries, and acceptance live in the policy
Skills, Agent profiles, current tool schemas, and main-agent diff inspection. Setup preserves unrelated
context, memory-routing, closeout, and user Hook groups.

Earlier project Hook assets are retired through the authenticated cleanup below. The installer
reads `hooks.json` only when it already exists and never creates it merely to represent this
project.

## 6. Retired project Agent and Hook assets

The former `frontend-design.toml` custom Agent is retired because the suite has no routing path for
it and the separately installed `frontend-design` Skill remains the appropriate capability entry.
The installer removes the old Agent profile only when its bytes match a known project version.
A modified or unrelated same-named profile is an ownership conflict and remains untouched.

Pure v2 verification rejects the former `subagent_guard.py`, `subagent_scope.py`, and project
`orchestration_route.py` assets.

The installer removes a retired file only when its bytes match a known prior project hash. It
removes a former registration only when the handler is an exact two-argument Python command, has a
known project event/matcher shape, and its referenced script has authenticated prior-project bytes.
The recognized shapes include the former Guard matchers, the `SubagentStart` Scope registration,
and the matcher-free project `UserPromptSubmit` Route registration. Both `command` and
`commandWindows` fields are inspected. An exact reference to a managed retired target outside
those known shapes blocks retirement so
setup cannot create a dangling custom registration. Project-shaped Hook command paths containing
`..`, relative syntax, or shell expansion characters are unsafe and conflict instead of being
normalized through an unchecked parent. Existing filesystem aliases are compared by file identity;
macOS case aliases are conservatively case-folded even after the target disappears. Every existing
physical script referenced by a recognized Python invocation or explicit command path is also
checked against known retired hashes. This includes statically recognizable absolute paths inside
environment wrappers or quoted command/code arguments. The installer does not execute or fully
interpret arbitrary wrapper code, constructed paths, or environment-variable values, so it does
not claim ownership from those alone. Ambiguous, missing, linked, or different same-named assets
remain conflicts. An unparseable command that names a retired project script also conflicts;
otherwise unrelated, well-formed Hook text that merely mentions a retired filename is preserved.

Reconciliation accepts strict UTF-8 JSON with or without a byte-order mark and rejects duplicate
keys, non-standard constants, non-object Hook maps, non-list events, and malformed group Hook lists.
It preserves unrelated top-level fields, events, matcher groups, handlers, and order.

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
manual command for a setup with global rules is:

```text
python3 scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root> --global-rules
```

With `--no-global-rules`, omit `--global-rules`.

Installation is complete only when required Skill and Agent copies match, any saved language or
model route is valid, no authenticated retired project Agent or Hook remains, and no
unapproved target was changed. Start a new Codex task after success so Skills, Agents, global rules,
and task instructions reload.
