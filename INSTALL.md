# Deterministic installation and uninstall contract

Use this contract when installing, updating, repairing, uninstalling, or verifying this checkout
for a local Codex environment. Read it completely before changing user configuration.

`scripts/install.py` is the only mutation implementation of this contract. In an interactive
terminal, it prints the complete plan and changes the runtime only after confirmation. In
non-interactive use, it plans by default and changes the runtime only with `--apply`. Do not
reproduce its projection or removal with ad hoc file commands.
The checkout remains the source of truth for portable Skills, Agents, the managed global-rules
block, and the deterministic installer. Installed files are runtime artifacts; task-package
language, model routes, unrelated Hook registrations, and unrelated user configuration stay local.

## 1. Choose the runtime targets

Use the Python interpreter available on the host (`python3`, `py -3`, or `python`). Python 3.9 or
newer is required.

The standard user targets require no path arguments:

- `--codex-home`: the active Codex home. An explicit value wins, then `CODEX_HOME`, then the
  documented Codex default `~/.codex`.
- `--skills-root`: the Skill root loaded by the current Codex runtime. An explicit value wins;
  otherwise the installer uses the documented user Skill root `~/.agents/skills`.

Pass explicit roots only for a non-standard runtime. Inspect current Codex configuration and
installed Skill listings when its active targets are not the documented defaults. Existing
deployment registries may record this checkout as the suite authority, but they must mark its
members as externally installed and leave runtime writes to this installer.

## 2. Plan before applying

On macOS, run:

```text
python3 scripts/install.py
```

On native Windows PowerShell, run:

```text
py -3 scripts/install.py
```

In an interactive terminal, a first install asks for `en` or `zh-CN` and suggests a default from the
system locale. It then validates the checkout, classifies every managed target, prints every
proposed create or update, shows the exact global-rules block, and reports conflicts. Answer `y` to
apply that exact plan; any other answer leaves the runtime unchanged. A later run preserves the
saved language and does not ask again. If every managed target is already current, setup exits
without asking for confirmation.

Non-interactive use never prompts and remains a dry run unless `--apply` is present. Its first
install must pass `--language en` or `--language zh-CN`. When an Agent performs the installation, it
shows the dry-run plan and obtains approval before adding `--apply`.

Explicit `--codex-home`, `--skills-root`, `--language`, and `--no-global-rules` arguments remain
available for non-standard or automated deployments. Passing a different language explicitly plans
that change.

To remove the globally installed current projection, run the same checkout with `--uninstall`:

```text
python3 scripts/install.py --uninstall
```

On native Windows use `py -3`. Interactive use prints the complete removal plan and asks for one
confirmation. Non-interactive use is likewise a dry run until `--apply` is added. Uninstall does
not use `--language`, and it rejects `--no-global-rules` because keeping the global routing block
while removing its Skills would leave unusable instructions.

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
plan. Uninstall also rejects either selected runtime root when it is inside, equal to, or an
ancestor of the source checkout, so a custom target cannot map managed deletions onto repository
sources. This overlap check uses filesystem identity as well as lexical containment, covering case
aliases on case-insensitive filesystems. Managed targets at or beyond the conservative native
Windows path limit are conflicts rather than partial long-path support. The installer never
intentionally traverses, unlinks, or replaces
links. A normal installation plan contains no delete operations: it writes only the named current
projection. Explicit `--uninstall` removes only current managed files whose bytes still match this
checkout, plus a well-formed marker-owned global-rules block. A changed managed file is a conflict
that blocks the whole removal plan. Both modes preserve every unmanaged Skill, Agent, Hook
registration, Hook file, model route, configuration key, and file.
New POSIX directories use mode `0700`; replacement preserves an existing POSIX file mode or
Windows file ACL and attributes.

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

Explicit `--uninstall` scans both global instruction candidates and removes one well-formed owned
block wherever it exists, including a stale block from an older release. Marker ownership is the
deletion authority; malformed or duplicated markers fail closed. Bytes outside the block remain
unchanged, and a global instruction file is retained even when removing the block leaves it empty.

## 5. No project Hook installation

This project installs no Hook. Worker authority, task boundaries, and acceptance live in the policy
Skills, Agent profiles, current tool schemas, and main-agent diff inspection. Setup does not read
`hooks.json`, inspect the Hook directory, or classify unmanaged Agent profiles. Existing context,
memory-routing, closeout, user Hook groups, and files from earlier project versions remain untouched.

Uninstall removes only the current named projection. Removing legacy runtime assets remains a
separate, user-directed maintenance action. Inspect and approve the exact files and registrations
outside this installer; installation or uninstall success makes no claim about them.

## 6. Local model routing

Setup does not create or change `<codex-home>/codex-orchestration/model-routing.toml`. Available
models, reasoning levels, and service-tier enforcement are host facts that must be verified live.

When local routing is wanted, start from `examples/model-routing.toml`, replace every placeholder
with supported host values, remove unused examples, review the complete file, and install it only
after explicit approval. An existing route remains local and is preserved by setup. Omitting model
selection requests inheritance from current Codex settings; it does not confirm the resolved model.

## 7. Transaction and conflicts

Within one running installer process, a caught mutation or verification failure before the
verified uninstall commit triggers rollback of the displayed managed file operations:

- Each write uses a same-directory temporary file and atomic replacement.
- Each uninstall deletion is first moved to a same-directory staged file and is permanently removed
  only after absence verification succeeds.
- The installer retains the pre-transaction bytes in memory.
- A caught mutation failure or failed verification restores completed target bytes and removes
  newly created empty directories where possible.
- A preflight conflict prevents all writes.

Successful absence verification is the uninstall commit point. The installer then removes every
staged copy. If operating-system attributes or another local process prevent that cleanup, the
named runtime remains uninstalled and the command succeeds with a warning that names the retained,
recoverable staged copy; it does not claim that post-commit cleanup was complete or attempt a
partial rollback after other staged copies may already be gone.

The plan is a snapshot, not a lock. Before each operation, the installer rechecks the physical
path and the target bytes captured during planning, and it rechecks the result after each operation.
A target that appears, disappears, changes, or gains a linked parent blocks the transaction. This
is not an operating-system security boundary against an adversarial same-user process; do not edit
or replace the selected runtime roots concurrently.

An abrupt process termination or power loss is not journaled and can leave a partial projection or
a same-directory installer temporary or staged file. After either event, stop concurrent editors,
inspect any such file before changing it, then run a fresh dry run and apply again only after the
plan is understood. Rollback restores managed bytes.

A one-time migration from links or a different checkout remains an explicit cutover. The installer
reports those paths as conflicts; the user first chooses the exact targets to move or unlink, then
runs a new dry run. Successful installation never implies permission to remove the old source.

## 8. Verification

`--apply` automatically runs source validation and the selected runtime checks. The equivalent
manual command for a setup with global rules is:

```text
python3 scripts/validate.py --runtime --codex-home <codex-home> --skills-root <skills-root> --global-rules
```

With `--no-global-rules`, omit `--global-rules`.

For `--uninstall`, verification instead requires every current managed Skill, Agent, and task
language file to be absent and requires both global instruction candidates to contain no owned
block. Unmanaged files inside a formerly managed directory may keep that directory in place.

Installation is complete only when required Skill and Agent copies match, any saved language or
model route is valid, and no unapproved target was changed. Uninstall is complete only after the
current named projection is absent without changing preserved local content. Start a new Codex task
after either operation so Skills, Agents, global rules, and task instructions reload.
