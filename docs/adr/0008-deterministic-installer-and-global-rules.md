# Adopt a deterministic installer and managed global rules

**Status:** accepted

## Context

The earlier Agent-only installation contract described safe outcomes but required every installing
Agent to reconstruct the same copying, Hook merge, ownership, and rollback behavior. That increased
variance across macOS and native Windows and made updates harder to audit. The installation model in
[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) demonstrated a useful boundary:
project-owned runtime files and prompt content can be reconciled deterministically while unrelated
user configuration remains outside the managed surface.

Codex does not support Claude Code's companion-file import syntax for global instructions. It reads
the first non-empty `AGENTS.override.md` or `AGENTS.md` in Codex home. Codex plugins can bundle Skills
and Hooks, but this suite also installs custom Agent profiles, so plugin packaging would still leave
a second installation path.

## Decision

Ship `scripts/install.py` as the deterministic implementation of `INSTALL.md`. It is dry-run by
default and writes only with `--apply`. The caller supplies the active Skill root; Codex home follows
the explicit argument, `CODEX_HOME`, or the documented Codex default. The installer classifies every
managed path, refuses linked or ambiguous targets, applies file changes atomically, and rolls the
completed transaction back when the running process catches a write or verification failure.

The canonical global prompt is `examples/global-agents-block.md`. Installation enables it by default
and owns only the exact marker-delimited block in the active global instruction file. Surrounding
bytes remain user-owned. Corrupt or duplicated markers fail closed, and a change in the active
override moves the managed block instead of leaving two copies.

At the time of this decision, the writer-lease Hook remained optional. When selected, the installer replaced only registrations
that invoke its exact managed script path, removes authenticated retired project registrations, and
preserves unrelated Hook handlers, event groups, ordering, and top-level JSON fields. Codex Hook
trust remains host-owned and must be reviewed through `/hooks` after installation.

The optional-Hook portion is superseded by
[ADR 0010](0010-retire-orchestration-hook-and-rigid-briefs.md). The later
[ADR 0012](0012-remove-legacy-cleanup-from-installation.md) removes authenticated retirement from
the installer and keeps all unmanaged Agent and Hook content outside its projection.

Model routing stays local and outside automated setup because availability and service-tier
enforcement require live host evidence. Symlink cutovers and ambiguous legacy ownership remain
explicit user decisions rather than `--apply` side effects.

The installer is not a journaled or hostile-local-process transaction boundary. Abrupt termination
can leave a partial projection, and concurrent replacement of selected roots is unsupported. The
documented recovery is a fresh dry run followed by an explicitly reviewed apply.

## Consequences

Installation and update now have one testable implementation shared by macOS and native Windows.
The managed policy pointers load consistently without replacing personal instructions, while the
full policies remain in their Skills. The repository gains installer and prompt-injection tests
and must keep `INSTALL.md`, both READMEs, runtime validation, and the canonical block synchronized.

The later split from one orchestration pointer to separate orchestration and Review pointers is
defined by [ADR 0011](0011-separate-delivery-review-from-orchestration.md).

This supersedes the former no-write-installer implementation choice while preserving ADR 0001's
repository authority and runtime-projection boundary.
